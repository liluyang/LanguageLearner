# Tool to improve language learning.

Project development is driven by AI vibe coding.

To download source code to your local, run
git clone https://github.com/liluyang/LanguageLearner.git

## Run

Streamlit is a lightweight python web framework, to run a web page driven by local python code and data.

```
streamlit run flashcard.py
```

## Installation

To run this program, following software is needed --

* streamlit package
* python 3.13.x, because streamlit support up to 3.13

Recommend to install above in virtual environment, otherwise you'll have a hard time to solve all python packages dependency
issues.

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

### How to get into virtual python mode and quit

```
# Get into virtual python mode
source .venv/bin/activate

# To quit
deactivate
```
