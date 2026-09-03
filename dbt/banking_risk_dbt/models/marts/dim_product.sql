with products as (

    select distinct

        product,
        sub_product

    from {{ ref('int_cfpb_complaints_enriched') }}

    where product is not null

)

select

    md5(
        lower(
            trim(product)
            || '|'
            || coalesce(trim(sub_product), '')
        )
    ) as product_key,

    product as product_name,

    sub_product as sub_product_name

from products