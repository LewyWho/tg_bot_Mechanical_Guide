from callbacks import yes_need_notification, no_need_notification, view_requests, back_page, next_page, my_requests, \
    search_by_tags, process_entering_tag, SearchTags


def all_callback(dp):
    dp.register_callback_query_handler(yes_need_notification, text='yes_need_notification')
    dp.register_callback_query_handler(no_need_notification, text='no_need_notification')
    dp.register_callback_query_handler(my_requests, text='my_requests')
    dp.register_callback_query_handler(view_requests, text='view_requests')
    dp.register_callback_query_handler(back_page, text='back_page')
    dp.register_callback_query_handler(next_page, text='next_page')
    dp.register_callback_query_handler(search_by_tags, text='search_by_tags')

    dp.register_message_handler(process_entering_tag, state=SearchTags.entering_tag)