def transform(prefix_key_list):
    int_key = prefix_key_list[0]
    index_key = prefix_key_list[1]
    transformed_key = f"{int_key}.{index_key}"
    return str(transformed_key)
