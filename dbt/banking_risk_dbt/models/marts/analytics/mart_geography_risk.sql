with geography_metrics as (

    select

        f.geography_key,

        d.state_code,

        count(*) as complaint_count,

        sum(f.timely_response_flag) as timely_responses,

        sum(f.untimely_response_flag) as untimely_responses,

        count(
            distinct f.company_key
        ) as distinct_companies,

        count(
            distinct f.product_key
        ) as distinct_products,

        count(
            distinct f.issue_key
        ) as distinct_issues

    from {{ ref('fct_complaints') }} f

    inner join {{ ref('dim_geography') }} d
        on f.geography_key = d.geography_key

    group by
        f.geography_key,
        d.state_code

),

geography_analytics as (

    select

        geography_key,

        state_code,

        complaint_count,

        round(
            100.0 * complaint_count
            / nullif(
                sum(complaint_count) over (),
                0
            ),
            2
        ) as complaint_share_pct,

        timely_responses,

        untimely_responses,

        round(
            100.0 * timely_responses
            / nullif(
                complaint_count,
                0
            ),
            2
        ) as timely_response_pct,

        round(
            100.0 * untimely_responses
            / nullif(
                complaint_count,
                0
            ),
            2
        ) as untimely_response_pct,

        distinct_companies,

        distinct_products,

        distinct_issues,

        dense_rank() over (
            order by complaint_count desc
        ) as state_rank

    from geography_metrics

)

select

    geography_key,
    state_code,
    complaint_count,
    complaint_share_pct,
    timely_responses,
    untimely_responses,
    timely_response_pct,
    untimely_response_pct,
    distinct_companies,
    distinct_products,
    distinct_issues,
    state_rank

from geography_analytics