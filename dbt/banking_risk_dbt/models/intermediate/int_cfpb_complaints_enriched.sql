with complaints as (

    select *
    from {{ ref('stg_cfpb_complaints') }}

),

enriched as (

    select

        raw_row_id,
        complaint_id,

        product,
        sub_product,
        issue,
        sub_issue,

        company,

        state,
        zip_code,

        submitted_via,

        company_response,
        company_public_response,

        complaint_narrative,
        tags,

        has_narrative,
        is_timely_response,

        received_at,
        sent_to_company_at,

        (received_at at time zone 'UTC')::date
    as received_date,

(sent_to_company_at at time zone 'UTC')::date
    as sent_to_company_date,

date_trunc(
    'month',
    received_at at time zone 'UTC'
)::date
    as received_month,

extract(
    year from received_at at time zone 'UTC'
)::integer
    as received_year,

extract(
    month from received_at at time zone 'UTC'
)::integer
    as received_month_number,

extract(
    quarter from received_at at time zone 'UTC'
)::integer
    as received_quarter,

        case
    when sent_to_company_at is not null
    then (
        (sent_to_company_at at time zone 'UTC')::date
        -
        (received_at at time zone 'UTC')::date
    )
    else null
end as days_to_send_to_company,

        case
            when has_narrative = true
            then 1
            else 0
        end as narrative_flag,

        case
            when is_timely_response = true
            then 1
            else 0
        end as timely_response_flag,

        case
            when is_timely_response = false
            then 1
            else 0
        end as untimely_response_flag,

        source_file,
        ingested_at

    from complaints

)

select *
from enriched