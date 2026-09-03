with companies as (

    select distinct
        company
    from {{ ref('int_cfpb_complaints_enriched') }}
    where company is not null

)

select

    md5(lower(trim(company))) as company_key,

    company as company_name

from companies