import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

N_TOPICS = 6
TOP_TERMS_PER_TOPIC = 8

RANDOM_STATE = 42


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    """
    Clean CFPB complaint narratives for NLP/topic modeling.
    Removes redaction artifacts and common boilerplate while
    preserving meaningful financial-service terminology.
    """

    if pd.isna(text):
        return ""

    text = str(text).lower()

    # Remove URLs
    text = re.sub(
        r"http\S+|www\.\S+",
        " ",
        text,
    )

    # Remove emails
    text = re.sub(
        r"\S+@\S+",
        " ",
        text,
    )

    # Remove CFPB redaction tokens such as XX, XXXX, XXXXXXXX
    text = re.sub(
        r"\b[xX]{2,}\b",
        " ",
        text,
    )

    # Remove sequences dominated by X/redaction characters
    text = re.sub(
        r"\b(?:xx\s*){2,}\b",
        " ",
        text,
    )

    # Remove standalone numbers
    text = re.sub(
        r"\b\d+\b",
        " ",
        text,
    )

    # Keep letters and spaces
    text = re.sub(
        r"[^a-z\s]",
        " ",
        text,
    )

    # Remove generic boilerplate words that add little topic value
    boilerplate_words = [
        "complaint",
        "consumer",
        "cfpb",
        "please",
        "thank",
        "thanks",
        "information",
        "received",
        "stated",
        "provided",
    ]

    for word in boilerplate_words:
        text = re.sub(
            rf"\b{word}\b",
            " ",
            text,
        )

    # Normalize whitespace
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text

# ============================================================
# SENTIMENT
# ============================================================

def sentiment_label(score):
    if score >= 0.05:
        return "Positive"

    if score <= -0.05:
        return "Negative"

    return "Neutral"


# ============================================================
# URGENCY
# ============================================================

URGENCY_PATTERNS = {
    "Fraud / Scam": [
        r"\bfraud\b",
        r"\bscam\b",
        r"\bidentity theft\b",
        r"\bstolen identity\b",
    ],

    "Unauthorized Activity": [
        r"\bunauthorized\b",
        r"\bnot authorized\b",
        r"\bdid not authorize\b",
    ],

    "Legal / Escalation": [
        r"\blawsuit\b",
        r"\battorney\b",
        r"\blegal action\b",
        r"\bcourt\b",
        r"\bsue\b",
    ],

    "Foreclosure / Repossession": [
        r"\bforeclosure\b",
        r"\brepossession\b",
        r"\brepossess\b",
        r"\beviction\b",
    ],

    "Immediate Financial Harm": [
        r"\burgent\b",
        r"\bemergency\b",
        r"\bimmediately\b",
        r"\bfinancial hardship\b",
        r"\bunable to pay\b",
    ],
}


def detect_urgency(text):
    text = str(text).lower()

    reasons = []

    for category, patterns in URGENCY_PATTERNS.items():

        for pattern in patterns:

            if re.search(pattern, text):
                reasons.append(category)
                break

    if reasons:
        return 1, " | ".join(reasons)

    return 0, None


# ============================================================
# FIND LATEST RAW FILE
# ============================================================

def get_latest_raw_file():

    files = list(
        RAW_DIR.glob(
            "cfpb_complaints_raw_*.csv"
        )
    )

    if not files:
        raise FileNotFoundError(
            "No CFPB raw CSV found in data/raw."
        )

    latest_file = max(
        files,
        key=lambda path: path.stat().st_mtime,
    )

    return latest_file


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n========================================"
    )
    print(
        "CFPB COMPLAINT NLP PIPELINE"
    )
    print(
        "========================================"
    )

    input_file = get_latest_raw_file()

    print(
        f"\nInput file:\n{input_file}"
    )

    df = pd.read_csv(
        input_file,
        dtype=str,
        low_memory=False,
    )

    print(
        f"\nRaw rows: {len(df):,}"
    )


    # ========================================================
    # REQUIRED COLUMNS
    # ========================================================

    required_columns = [
        "complaint_id",
        "complaint_what_happened",
        "date_received",
        "company",
        "product",
        "state",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )


    # ========================================================
    # KEEP ONLY COMPLAINTS WITH NARRATIVES
    # ========================================================

    df["complaint_what_happened"] = (
        df["complaint_what_happened"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    nlp_df = df[
        df["complaint_what_happened"] != ""
    ].copy()

    print(
        f"Complaints with narrative: "
        f"{len(nlp_df):,}"
    )

    if nlp_df.empty:
        raise ValueError(
            "No complaint narratives found."
        )


    # ========================================================
    # CLEAN TEXT
    # ========================================================

    print(
        "\nCleaning complaint narratives..."
    )

    nlp_df["cleaned_narrative"] = (
        nlp_df["complaint_what_happened"]
        .apply(clean_text)
    )

    nlp_df = nlp_df[
        nlp_df["cleaned_narrative"]
        .str.len()
        >= 20
    ].copy()

    nlp_df["narrative_word_count"] = (
        nlp_df["cleaned_narrative"]
        .str.split()
        .str.len()
    )


    # ========================================================
    # SENTIMENT ANALYSIS
    # ========================================================

    print(
        "Running sentiment analysis..."
    )

    sentiment_analyzer = (
        SentimentIntensityAnalyzer()
    )

    nlp_df["sentiment_score"] = (
        nlp_df["complaint_what_happened"]
        .apply(
            lambda text:
            sentiment_analyzer
            .polarity_scores(str(text))[
                "compound"
            ]
        )
    )

    nlp_df["sentiment_label"] = (
        nlp_df["sentiment_score"]
        .apply(sentiment_label)
    )


    # ========================================================
    # URGENCY FLAG
    # ========================================================

    print(
        "Detecting urgency / escalation language..."
    )

    urgency_results = (
        nlp_df["complaint_what_happened"]
        .apply(detect_urgency)
    )

    nlp_df["urgency_flag"] = [
        result[0]
        for result in urgency_results
    ]

    nlp_df["urgency_reason"] = [
        result[1]
        for result in urgency_results
    ]


    # ========================================================
    # TF-IDF
    # ========================================================

    print(
        "Creating TF-IDF matrix..."
    )

    vectorizer = TfidfVectorizer(
    stop_words="english",
    max_features=6000,
    min_df=5,
    max_df=0.90,
    ngram_range=(1, 2),
    sublinear_tf=True,
)

    tfidf_matrix = (
        vectorizer
        .fit_transform(
            nlp_df[
                "cleaned_narrative"
            ]
        )
    )


    # ========================================================
    # NMF TOPIC MODEL
    # ========================================================

    print(
        f"Training NMF topic model "
        f"with {N_TOPICS} topics..."
    )

    nmf_model = NMF(
        n_components=N_TOPICS,
        init="nndsvda",
        random_state=RANDOM_STATE,
        max_iter=400,
    )

    topic_matrix = (
        nmf_model
        .fit_transform(
            tfidf_matrix
        )
    )

    feature_names = (
        vectorizer
        .get_feature_names_out()
    )


    # ========================================================
    # TOP TERMS PER TOPIC
    # ========================================================

    topic_keywords = {}

    for topic_id, topic_weights in enumerate(
        nmf_model.components_
    ):

        top_indexes = (
            topic_weights
            .argsort()[
                -TOP_TERMS_PER_TOPIC:
            ][::-1]
        )

        keywords = [
            feature_names[index]
            for index in top_indexes
        ]

        topic_keywords[
            topic_id
        ] = keywords


    # ========================================================
    # ASSIGN TOPIC
    # ========================================================

    nlp_df["topic_id"] = (
        topic_matrix.argmax(axis=1)
    )

    nlp_df["topic_keywords"] = (
        nlp_df["topic_id"]
        .map(
            lambda topic:
            ", ".join(
                topic_keywords[topic]
            )
        )
    )

    # Temporary human-readable topic name.
    # We will rename these after inspecting the output.
    TOPIC_NAMES = {
    0: "Credit Reporting & Disputes",
    1: "Incorrect & Damaging Credit Entries",
    2: "Banking Service Issues",
    3: "Identity Theft & Fraud",
    4: "Regulatory & Reporting Accuracy",
    5: "Bank Account & Card Issues",
}

    nlp_df["topic_name"] = (
    nlp_df["topic_id"]
    .map(TOPIC_NAMES)
)


    # ========================================================
    # DATE FEATURES
    # ========================================================

    nlp_df["received_date"] = (
        pd.to_datetime(
            nlp_df["date_received"],
            errors="coerce",
        )
    )

    nlp_df["month_start_date"] = (
        nlp_df["received_date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )


    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    output_columns = [
        "complaint_id",
        "date_received",
        "month_start_date",
        "company",
        "product",
        "state",
        "sentiment_score",
        "sentiment_label",
        "topic_id",
        "topic_name",
        "topic_keywords",
        "urgency_flag",
        "urgency_reason",
        "narrative_word_count",
    ]

    final_df = (
        nlp_df[
            output_columns
        ]
        .copy()
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        PROCESSED_DIR
        / "complaint_nlp_features.csv"
    )

    final_df.to_csv(
        output_file,
        index=False,
    )


    # ========================================================
    # TOPIC SUMMARY
    # ========================================================

    topic_summary = (
        final_df
        .groupby(
            [
                "topic_id",
                "topic_name",
                "topic_keywords",
            ],
            as_index=False,
        )
        .agg(
            complaint_count=(
                "complaint_id",
                "nunique",
            ),

            avg_sentiment_score=(
                "sentiment_score",
                "mean",
            ),

            urgent_complaints=(
                "urgency_flag",
                "sum",
            ),
        )
        .sort_values(
            "complaint_count",
            ascending=False,
        )
    )

    topic_summary_file = (
        PROCESSED_DIR
        / "nlp_topic_summary.csv"
    )

    topic_summary.to_csv(
        topic_summary_file,
        index=False,
    )


    # ========================================================
    # QUALITY CHECK
    # ========================================================

    print(
        "\n========================================"
    )
    print(
        "NLP QUALITY CHECK"
    )
    print(
        "========================================"
    )

    print(
        f"NLP rows: "
        f"{len(final_df):,}"
    )

    print(
        "\nSentiment distribution:"
    )

    print(
        final_df[
            "sentiment_label"
        ]
        .value_counts()
    )

    print(
        "\nUrgency distribution:"
    )

    print(
        final_df[
            "urgency_flag"
        ]
        .value_counts()
    )

    print(
        "\nTopic summary:"
    )

    print(
        topic_summary[
            [
                "topic_id",
                "topic_name",
                "complaint_count",
                "avg_sentiment_score",
                "urgent_complaints",
            ]
        ]
        .to_string(
            index=False
        )
    )


    print(
        "\n========================================"
    )
    print(
        "NLP PIPELINE COMPLETE"
    )
    print(
        "========================================"
    )

    print(
        f"\nFeature file:\n"
        f"{output_file}"
    )

    print(
        f"\nTopic summary:\n"
        f"{topic_summary_file}"
    )


if __name__ == "__main__":
    main()