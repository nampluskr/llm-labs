from .clients import LangchainClient
from .webapp import main as _main


def main(argv=None):
    _main(LangchainClient, argv)


if __name__ == "__main__":
    main()
