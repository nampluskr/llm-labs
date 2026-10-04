from .clients import HttpClient
from .webapp import main as _main


def main(argv=None):
    _main(HttpClient, argv)


if __name__ == "__main__":
    main()
