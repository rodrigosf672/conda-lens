from pathlib import Path
import sys

# Ensure examples/scripts is on sys.path for local imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils.env_tools import get_env_summary

def main():
    summary = get_env_summary()
    print(summary)

if __name__ == "__main__":
    main()
