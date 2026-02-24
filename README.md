# Tool to improve language learning.

Project development is driven by AI vibe coding.

## Installation

### How to install python 3.13.x

I chose to download Mac installer from python.org, the reason to use 3.13 is: streamlit is claimed to be supported to 3.13.

After installation, you may find python3 --version still show "3.9.6" on Mac.

```
# Run this to set python3 to 3.13.x version.
source .bash_profile
```

### How to install streamlit

Streamlit is the framework to run flashcard.py

```
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install streamlit
```
