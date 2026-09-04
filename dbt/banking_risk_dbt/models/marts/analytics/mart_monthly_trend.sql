with monthly_metrics as (

    select

        d.month_start_date,

        d.year,

        d.month_number,

        max(d.month_name) as month_name,

        count(*) as complaint_count,

        sum(
            f.timely_response_flag
        ) as timely_responses,

        sum(
            f.untimely_response_flag
        ) as untimely_responses,

        count(
            distinct f.company_key
        ) as distinct_companies,

        count(
            distinct f.product_key
        ) as distinct_products,

        count(
            distinct f.issue_key
        ) as distinct_issues,

        count(
            distinct f.geography_key
        ) as distinct_states

    from {{ ref('fct_complaints') }} f

    inner join {{ ref('dim_date') }} d
        on f.received_date_key = d.date_key

    group by

        d.month_start_date,
        d.year,
        d.month_number

),

monthly_with_previous as (

    select

        month_start_date,

        year,

        month_number,

        month_name,

        complaint_count,

        lag(
            complaint_count
        ) over (
            order by month_start_date
        ) as previous_month_complaints,

        timely_responses,

        untimely_responses,

        distinct_companies,

        distinct_products,

        distinct_issues,

        distinct_states

    from monthly_metrics

),

monthly_analytics as (

    select

        month_start_date,

        year,

        month_number,

        month_name,

        complaint_count,

        previous_month_complaints,

        complaint_count
            - previous_month_complaints
            as month_over_month_change,

        round(
            100.0
            * (
                complaint_count
                - previous_month_complaints
            )
            / nullif(
                previous_month_complaints,
                0
            ),
            2
        ) as month_over_month_growth_pct,

        timely_responses,

        untimely_responses,

        round(
            100.0
            * timely_responses
            / nullif(
                complaint_count,
                0
            ),
            2
        ) as timely_response_pct,

        round(
            100.0
            * untimely_responses
            / nullif(
                complaint_count,
                0
            ),
            2
        ) as untimely_response_pct,

        distinct_companies,

        distinct_products,

        distinct_issues,

        distinct_states

    from monthly_with_previous

)

select

    month_start_date,

    year,

    month_number,

    month_name,

    complaint_count,

    previous_month_complaints,

    month_over_month_change,

    month_over_month_growth_pct,

    timely_responses,

    untimely_responses,

    timely_response_pct,

    untimely_response_pct,

    distinct_companies,

    distinct_products,

    distinct_issues,

    distinct_states

from monthly_analytics