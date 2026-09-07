with nlp as (

    select *
    from {{ ref('stg_complaint_nlp') }}

),

complaints as (

    select

        complaint_id,

        company_key,

        product_key,

        geography_key,

        received_date_key,

        received_date,

        state

    from {{ ref('fct_complaints') }}

),

final as (

    select

        n.complaint_id,

        c.company_key,

        c.product_key,

        c.geography_key,

        c.received_date_key,

        coalesce(
            c.received_date,
            n.date_received
        ) as received_date,

        n.month_start_date,

        coalesce(
            c.state,
            n.state
        ) as state,

        n.company,

        n.product,

        n.topic_id,

        n.topic_name,

        n.topic_keywords,

        n.sentiment_score,

        n.sentiment_label,

        n.urgency_flag,

        n.urgency_reason,

        n.narrative_word_count,

        case
            when n.sentiment_label = 'Negative'
            then 1
            else 0
        end as negative_sentiment_flag,

        case
            when n.sentiment_label = 'Neutral'
            then 1
            else 0
        end as neutral_sentiment_flag,

        case
            when n.sentiment_label = 'Positive'
            then 1
            else 0
        end as positive_sentiment_flag

    from nlp n

    inner join complaints c
        on n.complaint_id = c.complaint_id

)

select *
from final