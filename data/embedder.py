"""Shared embedder. One model for queries and corpus, enforced at load.

config/models.yaml embedding section is authoritative:
    model: BAAI/bge-base-en-v1.5, dim 768, normalize true, cosine,
    max_seq_length 512, query_instruction "" (none - matching is symmetric)

`one_model_rule` and `assert_at_load` in that file are the reason this module refuses to
run against a mismatched configuration rather than warning: a silent model swap between
indexing and query time would produce plausible-looking nonsense scores, and the
validation table would be quietly meaningless.
"""

import os
import sys

import numpy as np

DEFAULT_MODEL_PATH = os.path.expanduser("~/.cache/serendipity-lab/bge-base-en-v1.5")


def model_path():
    return os.environ.get("SERENDIPITY_MODEL_PATH", DEFAULT_MODEL_PATH)


def embedding_cfg(path="config/models.yaml"):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)["embedding"]


class Embedder:
    def __init__(self, cfg=None, device="cpu"):
        import yaml  # noqa: F401  (config already parsed by caller if given)
        self.cfg = cfg or embedding_cfg()
        p = model_path()
        if not os.path.isdir(p):
            raise SystemExit(
                f"embedding model not found at {p}\n"
                f"  fetch it, or set SERENDIPITY_MODEL_PATH to a directory containing it.")
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer(p, device=device)

        dim = self.m.get_sentence_embedding_dimension()
        if dim != int(self.cfg["dim"]):
            raise SystemExit(f"one_model_rule violated: model dim {dim} != configured "
                             f"{self.cfg['dim']}. Refusing to index/query a mismatched model.")
        self.dim = dim
        self.max_seq = int(self.cfg.get("max_seq_length", 512))
        if getattr(self.m, "max_seq_length", self.max_seq) != self.max_seq:
            self.m.max_seq_length = self.max_seq
        self.normalize = bool(self.cfg.get("normalize", True))
        if str(self.cfg.get("query_instruction", "")).strip():
            raise SystemExit(
                "query_instruction must be empty: matching is abstraction-to-abstraction, "
                "so neither side gets a prefix. An asymmetric instruction breaks symmetry.")

    def encode(self, texts, batch_size=None):
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        bs = int(batch_size or self.cfg.get("batch_size", 32))
        v = self.m.encode(list(texts), batch_size=bs,
                          normalize_embeddings=self.normalize,
                          show_progress_bar=False,
                          convert_to_numpy=True)
        return np.asarray(v, dtype=np.float32)

    def fingerprint(self):
        """Stored in Chroma collection metadata; loading refuses on mismatch."""
        return {
            "model": self.cfg["model"],
            "dim": int(self.cfg["dim"]),
            "normalize": bool(self.cfg.get("normalize", True)),
            "metric": self.cfg.get("metric", "cosine"),
            "max_seq_length": self.max_seq,
        }


if __name__ == "__main__":
    e = Embedder()
    v = e.encode(["structural test sentence", "another sentence entirely"])
    print("fingerprint:", e.fingerprint())
    print("shape:", v.shape, "unit-norm:", bool(np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-4)))
    print("cos(self,self) =", round(float(v[0] @ v[0]), 6))