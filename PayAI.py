import sys

from payai import main as _main


if __name__ == '__main__':
    _main.main()
else:
    sys.modules[__name__] = _main
