with source_data as (

    select *
    from {{ source('cfpb_raw', 'cfpb_complaints') }}

),

cleaned as (

    select

        raw_row_id,

        nullif(trim(complaint_id), '') as complaint_id,

        nullif(trim(product), '') as product,

        nullif(trim(sub_product), '') as sub_product,

        nullif(trim(issue), '') as issue,

        nullif(trim(sub_issue), '') as sub_issue,

        nullif(trim(company), '') as company,

        nullif(trim(state), '') as state,

        nullif(trim(zip_code), '') as zip_code,

        nullif(trim(submitted_via), '') as submitted_via,

        nullif(trim(company_response), '') as company_response,

        nullif(trim(company_public_response), '')
            as company_public_response,

        nullif(trim(complaint_what_happened), '')
            as complaint_narrative,

        nullif(trim(tags), '') as tags,

        case
            when lower(trim(has_narrative)) = 'true' then true
            when lower(trim(has_narrative)) = 'false' then false
            else null
        end as has_narrative,

        case
            when lower(trim(timely)) = 'yes' then true
            when lower(trim(timely)) = 'no' then false
            else null
        end as is_timely_response,

        nullif(trim(date_received), '')::timestamptz
            as received_at,

        nullif(trim(date_sent_to_company), '')::timestamptz
            as sent_to_company_at,

        source_file,

        ingested_at

    from source_data

)

select *
from cleaned