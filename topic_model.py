"""
LDA topic modelling on 2024 SSHRC Insight Grant titles (502 grants).
Loads titles from insight_titles_2024.json (extracted from open data CSV).
Outputs topic_assignments.json for use by build_treemap.py.
"""

import re, nltk, json
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

# NLTK data
nltk.download("stopwords", quiet=True)
nltk.download("wordnet", quiet=True)
try:
    from nltk.corpus import stopwords as _sw
    NLTK_STOPWORDS = set(_sw.words("english"))
except Exception:
    NLTK_STOPWORDS = set()
from nltk.stem import WordNetLemmatizer

_FALLBACK_SW = {
    "i","me","my","myself","we","our","ours","ourselves","you","your","yours",
    "yourself","yourselves","he","him","his","himself","she","her","hers",
    "herself","it","its","itself","they","them","their","theirs","themselves",
    "what","which","who","whom","this","that","these","those","am","is","are",
    "was","were","be","been","being","have","has","had","having","do","does",
    "did","doing","a","an","the","and","but","if","or","because","as","until",
    "while","of","at","by","for","with","about","against","between","into",
    "through","during","before","after","above","below","to","from","up","down",
    "in","out","on","off","over","under","again","further","then","once","here",
    "there","when","where","why","how","all","both","each","few","more","most",
    "other","some","such","no","nor","not","only","own","same","so","than",
    "too","very","s","t","can","will","just","don","should","now","d","ll",
    "m","o","re","ve","y","ain","aren","couldn","didn","doesn","hadn","hasn",
    "haven","isn","ma","mightn","mustn","needn","shan","shouldn","wasn",
    "weren","won","wouldn","new","use","using","used","also","may","many",
    "one","two","three","like","based","across","within","toward","towards",
    "among","through","via","per",
}
STOPWORDS = NLTK_STOPWORDS | _FALLBACK_SW

# Load titles from CSV-derived JSON
with open(r"C:\Users\calvi\policy-deep-dive-workspace\insight_titles_2024.json", encoding="utf-8") as f:
    titles = json.load(f)

print(f"Loaded {len(titles)} titles")

# Preprocessing
lemmatizer = WordNetLemmatizer()
stop_words = set(STOPWORDS)
stop_words.update([
    "study", "studies", "research", "using", "understanding", "exploring",
    "examining", "new", "canada", "canadian", "role", "impact", "effect",
    "effects", "analysis", "approach", "toward", "towards", "based", "case",
    "perspective", "perspectives", "evidence", "question", "making", "experience",
    "experiences", "understanding", "investigating", "developing", "building",
    "world", "across", "beyond", "within", "among", "way", "ways", "use",
    "used", "le", "la", "les", "de", "du", "en", "un", "une", "et", "dans",
    "pour", "par", "sur", "avec", "vers", "une", "aux", "des", "est", "sont",
    "entre", "chez", "lors", "leur", "leurs", "ces", "cette", "cet",
])

def preprocess(text):
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = text.split()
    tokens = [lemmatizer.lemmatize(t) for t in tokens
              if t not in stop_words and len(t) > 3]
    return " ".join(tokens)

processed = [preprocess(t) for t in titles]

# LDA
N_TOPICS = 9
vectorizer = CountVectorizer(max_df=0.85, min_df=2, max_features=800)
dtm = vectorizer.fit_transform(processed)
feature_names = vectorizer.get_feature_names_out()
print(f"Vocabulary size: {len(feature_names)}, Documents in DTM: {dtm.shape[0]}")

lda = LatentDirichletAllocation(
    n_components=N_TOPICS,
    random_state=42,
    max_iter=50,
    learning_method="batch",
)
lda.fit(dtm)

# Print top words per topic
print("\n-- LDA Topics (top 15 words each) --")
topic_top_words = []
for i, comp in enumerate(lda.components_):
    top_idx = comp.argsort()[-15:][::-1]
    words = [feature_names[j] for j in top_idx]
    topic_top_words.append(words)
    print(f"Topic {i+1:2d}: {', '.join(words)}")

# Assign each title to its dominant topic
doc_topics = lda.transform(dtm)
assignments = doc_topics.argmax(axis=1)
topic_counts = np.bincount(assignments, minlength=N_TOPICS)

print("\n-- Topic sizes --")
for i, (words, count) in enumerate(zip(topic_top_words, topic_counts)):
    print(f"Topic {i+1:2d} ({count:3d} titles): {', '.join(words[:6])}")

# Human labels - will be refined after seeing actual words
topic_labels = [
    "Economics & Governance",
    "Labour, Inequality & Wellbeing",
    "Ethics, Identity & Psychology",
    "Indigenous Rights & Politics",
    "Public Policy & Knowledge",
    "Community & Social Care",
    "Business, Innovation & Digital",
    "Justice, Culture & Corporations",
    "Climate, History & Education",
]

# Build per-topic title lists
topic_titles = {i: [] for i in range(N_TOPICS)}
for idx, assignment in enumerate(assignments):
    topic_titles[int(assignment)].append(titles[idx])

# Save
with open(r"C:\Users\calvi\policy-deep-dive-workspace\topic_assignments.json", "w", encoding="utf-8") as f:
    json.dump({
        "titles": titles,
        "assignments": assignments.tolist(),
        "topic_labels": topic_labels,
        "topic_top_words": topic_top_words,
        "topic_counts": topic_counts.tolist(),
        "topic_titles": {str(i): topic_titles[i] for i in range(N_TOPICS)},
    }, f, ensure_ascii=False, indent=2)

print("\n-- Suggested labels --")
for i, (label, count, words) in enumerate(zip(topic_labels, topic_counts, topic_top_words)):
    print(f"  {label} ({count}): {', '.join(words[:5])}")

print("\nSaved topic_assignments.json")
