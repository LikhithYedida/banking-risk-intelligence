with product_metrics as (

    select

        f.product_key,

        d.product_name,

        d.sub_product_name,

        count(*) as complaint_count,

        sum(f.timely_response_flag) as timely_responses,

        sum(f.untimely_response_flag) as untimely_responses,

        count(
            distinct f.company_key
        ) as distinct_companies,

        count(
            distinct f.issue_key
        ) as distinct_issues,

        count(
            distinct f.geography_key
        ) as distinct_states

    from {{ ref('fct_complaints') }} f

    inner join {{ ref('dim_product') }} d
        on f.product_key = d.product_key

    group by
        f.product_key,
        d.product_name,
        d.sub_product_name

),

product_analytics as (

    select

        product_key,

        product_name,

        sub_product_name,

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

        distinct_issues,

        distinct_states,

        dense_rank() over (
            order by complaint_count desc
        ) as product_rank

    from product_metrics

)

select

    product_key,
    product_name,
    sub_product_name,
    complaint_count,
    complaint_share_pct,
    timely_responses,
    untimely_responses,
    timely_response_pct,
    untimely_response_pct,
    distinct_companies,
    distinct_issues,
    distinct_states,
    product_rank

from product_analytics