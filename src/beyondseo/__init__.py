"""BeyondSEO — website crawling, readable content and SEO evidence."""

__version__ = "2.7.0"
__all__ = ["Config", "Crawler", "__version__"]


def __getattr__(name):
    if name == "Config":
        from .network import Config

        return Config
    if name == "Crawler":
        from .engine import Crawler

        return Crawler
    raise AttributeError(name)
