with geography as (

    select distinct

        coalesce(
            nullif(trim(state), ''),
            'UNKNOWN'
        ) as state_code

    from {{ ref('int_cfpb_complaints_enriched') }}

)

select

    md5(
        lower(state_code)
    ) as geography_key,

    state_code

from geography