with fact_total as (

    select
        count(*) as complaint_count

    from {{ ref('fct_complaints') }}

),

mart_total as (

    select
        sum(complaint_count) as complaint_count

    from {{ ref('mart_monthly_trend') }}

)

select

    fact_total.complaint_count as fact_complaints,

    mart_total.complaint_count as mart_complaints

from fact_total
cross join mart_total

where fact_total.complaint_count
    <> mart_total.complaint_count