with source as (

    select *
    from {{ source('cfpb_raw', 'complaint_nlp_features') }}

),

cleaned as (

    select

        complaint_id::text as complaint_id,

        date_received::date as date_received,

        month_start_date::date as month_start_date,

        nullif(
            trim(company),
            ''
        ) as company,

        nullif(
            trim(product),
            ''
        ) as product,

        nullif(
            trim(state),
            ''
        ) as state,

        sentiment_score::numeric as sentiment_score,

        trim(sentiment_label) as sentiment_label,

        topic_id::integer as topic_id,

        trim(topic_name) as topic_name,

        topic_keywords,

        urgency_flag::integer as urgency_flag,

        urgency_reason,

        narrative_word_count::integer as narrative_word_count,

        loaded_at

    from source

)

select *
from cleaned