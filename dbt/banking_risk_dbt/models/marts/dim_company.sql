with source_companies as (

    select

        trim(company) as company_name,

        lower(
            trim(company)
        ) as normalized_company_name

    from {{ ref('int_cfpb_complaints_enriched') }}

    where company is not null
      and trim(company) <> ''

),

companies as (

    select

        normalized_company_name,

        min(company_name) as company_name

    from source_companies

    group by normalized_company_name

)

select

    md5(
        normalized_company_name
    ) as company_key,

    company_name

from companies