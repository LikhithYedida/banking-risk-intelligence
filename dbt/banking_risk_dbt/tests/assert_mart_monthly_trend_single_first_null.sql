with monthly_data as (

    select
        month_start_date,
        previous_month_complaints,
        row_number() over (
            order by month_start_date
        ) as month_sequence

    from {{ ref('mart_monthly_trend') }}

)

select *

from monthly_data

where

    (
        month_sequence = 1
        and previous_month_complaints is not null
    )

    or

    (
        month_sequence > 1
        and previous_month_complaints is null
    )