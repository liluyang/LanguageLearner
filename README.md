# Tool to improve language learning.

Project development is driven by AI vibe coding. It helps user to memorize vocabulary in effective way.

## Data 

* New words: words from new_words.txt, each entry is in format of word : meaning : example
* Review: words from to_practice.txt, word only
* Day 5: words from difficult_5.txt, word only
* Day 15: words from difficult_15.txt, word only
* Today: words from today.txt, word only
* Dictionary: store in dictionary.txt, all words in format of word : meaning : example

## Learning Process

* Prepare above text files in data/ directory. Repository files are example only.
* New words are collection of words user learned recently, haven't been put into dictionary yet. A random word is picked from this pool and shown.
  * If you know, click "I know", and word will be move out of new_words.txt and store in dictionary.txt
  * If you want a example sentence as hint, click "Hint", and example sentence will be shown
  * If you are not sure whether you really know, click "Verify", and both meaning and example will be shown
  * If you don't remember, click "Don't know", and word will be move out of new_words.txt, store in dictionary.txt, and also today.txt and day_5.txt
* Why Day 5? according to learning theory, you should visit words that you can't remember after 5-day.
  * If you remember now, push it to difficult_15.txt, you will see it again after 15-day.
  * If you still cannot remember, keep it in difficult_5.txt, and you will see it after another 5-day.
* Day 15, similar process as Day 5, they are collection of words you should visit after 15-day.
* Today, that's collection of words that you missed today, keep retry to clear them.

Learning theory shows that new word -> 5 day revisit -> see it again in 15 day, that's the most efficient way for neural system store the word with strong signal. 

## Installation

To download source code to your local, run

```
git clone https://github.com/liluyang/LanguageLearner.git
```

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

## Run

Streamlit is a lightweight python web framework, to run a web page driven by local python code and data.

```
streamlit run flashcard.py
```

### How to get into virtual python mode and quit

```
# Get into virtual python mode
source .venv/bin/activate

# To quit
deactivate
```
