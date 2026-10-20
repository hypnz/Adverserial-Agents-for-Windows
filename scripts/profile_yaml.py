"""Parse Hermes YAML with the isolated adapter interpreter; never print its contents."""
import json
import sys


def main():
    try:
        from ruamel.yaml import YAML
    except ImportError:
        print(json.dumps({'error': 'missing_parser'}))
        return 1
    try:
        parser = YAML(typ='safe', pure=True)
        parser.version = (1, 1)  # Same schema as Hermes 0.22.2.
        value = parser.load(sys.stdin.read())
        if value is None: value = {}
        if not isinstance(value, dict):
            raise ValueError('mapping required')
        result = json.dumps({'config': value}, allow_nan=False)
    except Exception as error:
        mark = getattr(error, 'problem_mark', None)
        result = json.dumps({'error': 'invalid_yaml', 'line': getattr(mark, 'line', -1) + 1,
                             'column': getattr(mark, 'column', -1) + 1})
        print(result)
        return 1
    print(result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
