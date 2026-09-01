import hashlib
import math
import re
from datetime import datetime
from typing import Any
from backend.kb.chroma_client import get_embedding_model, get_chroma_client, get_kb_collection

# Smaller chunks than the original 800 words. An 800-word chunk dilutes both
# the embedding signal and the lexical term frequencies — the specific
# clause the advisor wants ends up averaged together with a page of adjacent
# text. ~220 words keeps a clause coherent while staying well under the
# embedding model's window. NOTE: chunk size only affects NEW uploads;
# documents already in the collection keep their original chunking until
# re-uploaded (Knowledge base → re-upload the file, or call reindex).
CHUNK_SIZE = 220
CHUNK_OVERLAP = 40
MIN_SIMILARITY = 0.35

# Reciprocal-rank-fusion constant. 60 is the value from the original RRF
# paper and is the de-facto default; it damps the contribution of low ranks
# so the top of each list dominates without any single list winning outright.
_RRF_K = 60

# English stopwords dropped from the lexical index/query so BM25 scores on
# content words, not "the"/"of"/"a". Deliberately small — we keep domain
# words like "trust", "relief", "tax".
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the",
    "to", "was", "were", "will", "with", "what", "which", "how", "do", "does",
    "can", "i", "you", "we", "they", "this", "these", "those", "if", "but",
}

# Unit words that follow a number: "2.5mn", "USD 5bn", "£325k". We expand
# them to a canonical long form so a query written "2.5mn" retrieves an
# article written "2.5 Mn" / "2.5 million". This is the crux of the
# "2.5mn UK business relief" recall gap: pure embeddings treat "2.5mn" and
# "2.5 Mn Business Property Relief" as only weakly related.
_UNIT_SYNONYMS = {
    "m": "million", "mn": "million", "mm": "million", "million": "million",
    "b": "billion", "bn": "billion", "billion": "billion",
    "k": "thousand", "thousand": "thousand",
}
_NUM_UNIT_RE = re.compile(r"(\d[\d.,]*)\s*(mm|mn|bn|m|b|k|million|billion|thousand)\b")
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.,][a-z0-9]+)*")


def _tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens with number-unit expansion.

    "2.5mn" → ["2.5mn", "2.5", "million"] so it overlaps a document that
    writes "2.5 Mn" (→ ["2.5", "mn", "million"]). Stopwords dropped.
    """
    low = text.lower()
    tokens = [t for t in _TOKEN_RE.findall(low) if t not in _STOPWORDS]
    extras: list[str] = []
    for m in _NUM_UNIT_RE.finditer(low):
        num, unit = m.group(1), m.group(2)
        canonical = _UNIT_SYNONYMS.get(unit, unit)
        extras.append(num)
        extras.append(canonical)
    return tokens + extras


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    while i < len(words):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        chunks.append(chunk)
        i += step
    return [c for c in chunks if c.strip()]


# ── Lexical (BM25) index ──────────────────────────────────────────────
#
# ChromaDB 0.5.x has no built-in keyword search, so we keep a small in-memory
# BM25 index alongside the vector collection and fuse the two rankings. The
# index is cached at module level keyed by a signature of the collection's
# ids, so it survives across the per-request KBManager instances and only
# rebuilds when documents are added or removed.

class _BM25:
    """Minimal BM25 (Okapi) over an in-memory corpus of token lists."""

    __slots__ = ("k1", "b", "corpus_tokens", "doc_len", "avgdl", "df", "idf", "N")

    def __init__(self, corpus_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = corpus_tokens
        self.N = len(corpus_tokens)
        self.doc_len = [len(t) for t in corpus_tokens]
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0
        self.df: dict[str, int] = {}
        for toks in corpus_tokens:
            for term in set(toks):
                self.df[term] = self.df.get(term, 0) + 1
        self.idf: dict[str, float] = {}
        for term, df in self.df.items():
            # BM25+ style idf; floored at a small positive value so a term
            # present in every doc still contributes a little.
            self.idf[term] = math.log(1 + (self.N - df + 0.5) / (df + 0.5))

    def scores(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.N
        q_terms = [t for t in query_tokens if t in self.idf]
        if not q_terms:
            return scores
        for i, toks in enumerate(self.corpus_tokens):
            if not toks:
                continue
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            dl = self.doc_len[i]
            denom_norm = self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
            s = 0.0
            for term in q_terms:
                f = tf.get(term)
                if not f:
                    continue
                s += self.idf[term] * (f * (self.k1 + 1)) / (f + denom_norm)
            scores[i] = s
        return scores


# module-level cache: {"sig": str, "index": _LexicalIndex}
_LEX_CACHE: dict[str, Any] = {"sig": None, "index": None}


class _LexicalIndex:
    __slots__ = ("ids", "documents", "metadatas", "bm25")

    def __init__(self, ids, documents, metadatas):
        self.ids = ids
        self.documents = documents
        self.metadatas = metadatas
        self.bm25 = _BM25([_tokenize(d or "") for d in documents])

    def search(self, query: str, top_k: int, jurisdiction: str | None) -> list[dict[str, Any]]:
        if not self.ids:
            return []
        scores = self.bm25.scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[dict[str, Any]] = []
        for i in ranked:
            if scores[i] <= 0:
                break
            meta = self.metadatas[i] or {}
            if jurisdiction and meta.get("jurisdiction") != jurisdiction:
                continue
            out.append({
                "id": self.ids[i],
                "text": self.documents[i],
                "bm25": scores[i],
                "meta": meta,
            })
            if len(out) >= top_k:
                break
        return out


class KBManager:
    def __init__(self, chroma_path: str | None = None):
        self.client = get_chroma_client(chroma_path)
        self.collection = get_kb_collection(self.client)
        self.model = get_embedding_model()

    # ── lexical index management ──────────────────────────────────────
    def _lexical_index(self) -> _LexicalIndex:
        """Return a BM25 index over the whole collection, rebuilding only when
        the set of document ids has changed."""
        raw = self.collection.get(include=["documents", "metadatas"])
        ids = raw.get("ids") or []
        sig = hashlib.md5(
            ("|".join(sorted(ids))).encode() if ids else b"empty"
        ).hexdigest()
        cached = _LEX_CACHE.get("index")
        if _LEX_CACHE.get("sig") == sig and cached is not None:
            return cached
        index = _LexicalIndex(ids, raw.get("documents") or [], raw.get("metadatas") or [])
        _LEX_CACHE["sig"] = sig
        _LEX_CACHE["index"] = index
        return index

    @staticmethod
    def _invalidate_lexical_cache() -> None:
        _LEX_CACHE["sig"] = None
        _LEX_CACHE["index"] = None

    async def upload_kb_file(
        self,
        content: str,
        source_file: str,
        jurisdiction: str,
        topic: str,
        last_updated: str | None = None,
        source_type: str = "kb_upload",
    ) -> int:
        # Delete existing chunks for this file
        existing = self.collection.get(where={"source_file": source_file})
        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])

        chunks = _chunk_text(content)
        if not chunks:
            self._invalidate_lexical_cache()
            return 0

        embeddings = self.model.encode(chunks).tolist()
        ids = [f"{source_file}_{i}_{hashlib.md5(c.encode()).hexdigest()[:8]}" for i, c in enumerate(chunks)]
        metadatas = [
            {
                "source_file": source_file,
                "jurisdiction": jurisdiction,
                "topic": topic,
                "last_updated": last_updated or datetime.utcnow().isoformat(),
                "source_type": source_type,
            }
            for _ in chunks
        ]
        self.collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
        self._invalidate_lexical_cache()
        return len(chunks)

    async def list_documents(self) -> list[dict[str, Any]]:
        """Return one entry per unique source_file with metadata."""
        result = self.collection.get(include=["metadatas"])
        seen: dict[str, dict] = {}
        for meta in result["metadatas"]:
            sf = meta.get("source_file", "unknown")
            if sf not in seen:
                seen[sf] = {
                    "source_file": sf,
                    "jurisdiction": meta.get("jurisdiction", ""),
                    "topic": meta.get("topic", ""),
                    "last_updated": meta.get("last_updated", ""),
                    "source_type": meta.get("source_type", ""),
                    "chunk_count": 1,
                }
            else:
                seen[sf]["chunk_count"] += 1
        return sorted(seen.values(), key=lambda x: x["last_updated"], reverse=True)

    async def delete_document(self, source_file: str) -> int:
        """Delete all chunks for a given source_file. Returns number deleted."""
        existing = self.collection.get(where={"source_file": source_file})
        if not existing["ids"]:
            return 0
        self.collection.delete(ids=existing["ids"])
        self._invalidate_lexical_cache()
        return len(existing["ids"])

    async def query(self, query: str, n_results: int = 5, jurisdiction: str | None = None) -> list[dict[str, Any]]:
        """Hybrid retrieval: dense (embedding) + lexical (BM25), fused with
        reciprocal rank fusion.

        Pure vector search misses exact keyword / acronym / number matches
        (e.g. "2.5mn UK business relief" failing to find an article titled
        "UK 2.5 Mn Business Property Relief (BPR)"). The lexical arm catches
        those; the dense arm catches paraphrases the lexical arm would miss.
        RRF combines the two rankings without needing the scores to be on a
        comparable scale.
        """
        # Fetch a wider candidate pool from each arm than we ultimately return,
        # so fusion has room to promote an item that ranks mid-list in one arm
        # but top in the other.
        pool = max(n_results * 4, 20)

        # ── Dense arm ──
        embedding = self.model.encode([query]).tolist()
        where = {"jurisdiction": jurisdiction} if jurisdiction else None
        vector_hits: dict[str, dict[str, Any]] = {}
        vector_rank: dict[str, int] = {}
        try:
            results = self.collection.query(
                query_embeddings=embedding,
                n_results=pool,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            ids0 = results.get("ids", [[]])[0]
            for rank, (cid, doc, meta, dist) in enumerate(zip(
                ids0,
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                similarity = 1 - dist
                vector_hits[cid] = {
                    "id": cid, "text": doc, "similarity": similarity, "meta": meta or {},
                }
                vector_rank[cid] = rank
        except Exception:
            vector_hits, vector_rank = {}, {}

        # ── Lexical arm ──
        lexical_rank: dict[str, int] = {}
        try:
            lex = self._lexical_index().search(query, top_k=pool, jurisdiction=jurisdiction)
        except Exception:
            lex = []
        for rank, hit in enumerate(lex):
            cid = hit["id"]
            lexical_rank[cid] = rank
            if cid not in vector_hits:
                vector_hits[cid] = {
                    "id": cid, "text": hit["text"], "similarity": None, "meta": hit["meta"],
                }

        if not vector_hits:
            return []

        # ── Reciprocal rank fusion ──
        fused: list[tuple[float, str]] = []
        for cid, entry in vector_hits.items():
            score = 0.0
            if cid in vector_rank:
                score += 1.0 / (_RRF_K + vector_rank[cid])
            if cid in lexical_rank:
                score += 1.0 / (_RRF_K + lexical_rank[cid])
            fused.append((score, cid))
        fused.sort(key=lambda t: t[0], reverse=True)

        output: list[dict[str, Any]] = []
        for _, cid in fused:
            entry = vector_hits[cid]
            sim = entry["similarity"]
            is_lexical = cid in lexical_rank
            # Keep a doc if it clears the dense-similarity floor OR it was a
            # genuine lexical match. This is what stops the 0.35 floor from
            # silently dropping a strong keyword hit that embeds weakly.
            if sim is not None and sim >= MIN_SIMILARITY:
                reported = sim
            elif is_lexical:
                # Lexical-only (or weakly-dense) hit: surface it with a
                # moderate confidence so it clears typical display thresholds
                # without overstating a pure keyword match.
                reported = max(sim or 0.0, 0.45)
            else:
                continue
            meta = entry["meta"] or {}
            output.append({"text": entry["text"], "similarity": reported, **meta})
            if len(output) >= n_results:
                break
        return output

    async def reindex_all(self) -> int:
        """Rebuild the lexical index from the current collection. Vector
        embeddings are unaffected (they live in Chroma). Returns doc count."""
        self._invalidate_lexical_cache()
        idx = self._lexical_index()
        return len(idx.ids)
