with base_companies as (

    select count(*) as company_count
    from {{ ref('mart_company_risk') }}

),

scored_companies as (

    select count(*) as company_count
    from {{ ref('mart_company_risk_score') }}

)

select
    base_companies.company_count as base_company_count,
    scored_companies.company_count as scored_company_count

from base_companies
cross join scored_companies

where base_companies.company_count
    <> scored_companies.company_count