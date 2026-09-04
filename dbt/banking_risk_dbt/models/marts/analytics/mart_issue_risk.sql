with issue_metrics as (

    select

        f.issue_key,

        d.issue_name,

        d.sub_issue_name,

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
            distinct f.geography_key
        ) as distinct_states

    from {{ ref('fct_complaints') }} f

    inner join {{ ref('dim_issue') }} d
        on f.issue_key = d.issue_key

    group by
        f.issue_key,
        d.issue_name,
        d.sub_issue_name

),

issue_analytics as (

    select

        issue_key,

        issue_name,

        sub_issue_name,

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

        distinct_states,

        dense_rank() over (
            order by complaint_count desc
        ) as issue_rank

    from issue_metrics

)

select

    issue_key,
    issue_name,
    sub_issue_name,
    complaint_count,
    complaint_share_pct,
    timely_responses,
    untimely_responses,
    timely_response_pct,
    untimely_response_pct,
    distinct_companies,
    distinct_products,
    distinct_states,
    issue_rank

from issue_analytics