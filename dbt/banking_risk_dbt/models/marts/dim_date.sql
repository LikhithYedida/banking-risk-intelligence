with date_bounds as (

    select

        min(received_date) as min_date,
        max(received_date) as max_date

    from {{ ref('int_cfpb_complaints_enriched') }}

),

date_spine as (

    select

        generate_series(
            min_date,
            max_date,
            interval '1 day'
        )::date as calendar_date

    from date_bounds

)

select

    to_char(
        calendar_date,
        'YYYYMMDD'
    )::integer as date_key,

    calendar_date,

    extract(
        year from calendar_date
    )::integer as year,

    extract(
        quarter from calendar_date
    )::integer as quarter,

    extract(
        month from calendar_date
    )::integer as month_number,

    trim(
        to_char(calendar_date, 'Month')
    ) as month_name,

    to_char(
        calendar_date,
        'Mon'
    ) as month_short_name,

    date_trunc(
        'month',
        calendar_date
    )::date as month_start_date,

    extract(
        week from calendar_date
    )::integer as week_of_year,

    extract(
        day from calendar_date
    )::integer as day_of_month,

    trim(
        to_char(calendar_date, 'Day')
    ) as day_name,

    extract(
        isodow from calendar_date
    )::integer as day_of_week_number,

    case
        when extract(isodow from calendar_date) in (6, 7)
        then true
        else false
    end as is_weekend

from date_spine