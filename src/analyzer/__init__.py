"""Phase-1 analyzer package."""

import os


# Configure TensorFlow GPU allocator defaults early so model stages can coexist.
# These defaults are only applied when the user/environment has not set them.
os.environ.setdefault("TF_GPU_ALLOCATOR", "cuda_malloc_async")
os.environ.setdefault("TF_FORCE_GPU_ALLOW_GROWTH", "true")

__all__ = ["__version__"]

__version__ = "0.1.0"
