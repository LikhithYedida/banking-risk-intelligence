with submission_channels as (

    select distinct

        coalesce(
            nullif(trim(submitted_via), ''),
            'UNKNOWN'
        ) as submission_channel

    from {{ ref('int_cfpb_complaints_enriched') }}

)

select

    md5(
        lower(submission_channel)
    ) as submission_channel_key,

    submission_channel

from submission_channels