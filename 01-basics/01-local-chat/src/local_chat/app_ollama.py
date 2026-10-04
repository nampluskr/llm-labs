from .clients import OllamaClient
from .webapp import main as _main


def main(argv=None):
    _main(OllamaClient, argv)


if __name__ == "__main__":
    main()
