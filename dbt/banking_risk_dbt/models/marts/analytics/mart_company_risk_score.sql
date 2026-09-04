with base as (

    select *
    from {{ ref('mart_company_risk') }}

),

ranges as (

    select

        min(complaint_count) as min_complaints,
        max(complaint_count) as max_complaints,

        min(distinct_products) as min_products,
        max(distinct_products) as max_products,

        min(distinct_issues) as min_issues,
        max(distinct_issues) as max_issues,

        min(distinct_states) as min_states,
        max(distinct_states) as max_states,

        min(untimely_response_pct) as min_untimely_pct,
        max(untimely_response_pct) as max_untimely_pct

    from base

),

normalized as (

    select

        b.*,

        case
            when r.max_complaints = r.min_complaints
                then 0
            else
                100.0
                * (b.complaint_count - r.min_complaints)
                / nullif(
                    r.max_complaints - r.min_complaints,
                    0
                )
        end as complaint_volume_score,

        case
            when r.max_products = r.min_products
                then 0
            else
                100.0
                * (b.distinct_products - r.min_products)
                / nullif(
                    r.max_products - r.min_products,
                    0
                )
        end as product_exposure_score,

        case
            when r.max_issues = r.min_issues
                then 0
            else
                100.0
                * (b.distinct_issues - r.min_issues)
                / nullif(
                    r.max_issues - r.min_issues,
                    0
                )
        end as issue_exposure_score,

        case
            when r.max_states = r.min_states
                then 0
            else
                100.0
                * (b.distinct_states - r.min_states)
                / nullif(
                    r.max_states - r.min_states,
                    0
                )
        end as geography_exposure_score,

        case
            when r.max_untimely_pct = r.min_untimely_pct
                then 0
            else
                100.0
                * (
                    b.untimely_response_pct
                    - r.min_untimely_pct
                )
                / nullif(
                    r.max_untimely_pct
                    - r.min_untimely_pct,
                    0
                )
        end as response_risk_score

    from base b

    cross join ranges r

),

scored as (

    select

        *,

        round(
              0.45 * complaint_volume_score
            + 0.20 * issue_exposure_score
            + 0.15 * product_exposure_score
            + 0.10 * geography_exposure_score
            + 0.10 * response_risk_score,
            2
        ) as risk_score

    from normalized

),

final as (

    select

        company_key,
        company_name,

        complaint_count,
        complaint_share_pct,

        timely_responses,
        untimely_responses,
        timely_response_pct,
        untimely_response_pct,

        distinct_products,
        distinct_issues,
        distinct_states,

        company_rank,

        round(complaint_volume_score, 2)
            as complaint_volume_score,

        round(product_exposure_score, 2)
            as product_exposure_score,

        round(issue_exposure_score, 2)
            as issue_exposure_score,

        round(geography_exposure_score, 2)
            as geography_exposure_score,

        round(response_risk_score, 2)
            as response_risk_score,

        risk_score,

        case

            when risk_score >= 70
                then 'High'

            when risk_score >= 40
                then 'Medium'

            else 'Low'

        end as risk_tier

    from scored

)

select *
from final