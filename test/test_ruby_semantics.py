import pytest
from atom_tools.lib import HttpRoute
from atom_tools.lib.ruby_semantics import code_to_routes, fix_url_params, find_constraints


def test_find_constraints():
    test_data = [
        'scope ":account_id", as: "account", constraints: { account_id: /\\d+/ } do resources :articles end',
        'get "photos/:id", to: "photos#show", constraints: { id: /[A-Z]\\d{5}/ }',
        'get "photos/:id", to: "photos#show", id: /[A-Z]\\d{5}/',
        'get "/:id", to: "articles#show", constraints: { id: /^\\d/ }',
        'get "/:id", to: "articles#show", constraints: { id: /\\d.+/ }',
        'get "/:year/:month/:slug", to: "articles#show", constraints: { year: /\\d{4}/, month: /\\d{2}/ }'
    ]
    for t in test_data:
        assert find_constraints(t)


def test_code_to_routes():
    assert code_to_routes(None) == []
    assert code_to_routes("") == []
    assert code_to_routes("Railsgoat::Application.routes.draw do") == []
    assert code_to_routes(
        'create_table \"analytics\", force: :cascade do |t| t.string \"ip_address\" t.string \"referrer\" t.string \"user_agent\" t.datetime \"created_at\" t.datetime \"updated_at\" end') == []
    assert code_to_routes('Railsgoat::Application.routes.draw do get \"login\" => ...') == [
        HttpRoute(url_pattern='/login', method='GET')]
    assert code_to_routes(
        'Railsgoat::Application.routes.draw do get \"login\" => \"sessions#new\" get \"signup\" => \"users#new\" get \"logout\" => \"sessions#destroy\" get \"forgot_password\" => \"password_resets#forgot_password\" post \"forgot_password\" => \"password_resets#send_forgot_password\" get \"password_resets\" => \"password_resets#confirm_token\" post \"password_resets\" => \"password_resets#reset_password\" get \"dashboard/doc\" => \"dashboard#doc\"') == [
               HttpRoute(url_pattern='/login', method='GET'),
               HttpRoute(url_pattern='/signup', method='GET'),
               HttpRoute(url_pattern='/logout', method='GET'),
               HttpRoute(url_pattern='/forgot_password', method='GET'),
               HttpRoute(url_pattern='/forgot_password', method='POST'),
               HttpRoute(url_pattern='/password_resets', method='GET'),
               HttpRoute(url_pattern='/password_resets', method='POST'),
               HttpRoute(url_pattern='/dashboard/doc', method='GET')]
    assert code_to_routes("""Rails.application.routes.draw do root \"home#index\" get \"/articles\", to: \"articles#index\" get '/oauth2-callback', to: 'o_auth#oauth_callback' get '/logout', to: 'o_auth#logout' get '/login', to: 'o_auth#login' get '/register', to: 'o_auth#register' get '/endsession', to: 'o_auth#endsession' end""") == [
        HttpRoute(url_pattern='/articles', method='GET'),
        HttpRoute(url_pattern='/oauth2-callback', method='GET'),
        HttpRoute(url_pattern='/logout', method='GET'),
        HttpRoute(url_pattern='/login', method='GET'),
        HttpRoute(url_pattern='/register', method='GET'),
        HttpRoute(url_pattern='/endsession', method='GET')
    ]


def test_code_to_routes_dangling():
    assert code_to_routes(
        'Railsgoat::Application.routes.draw do get \"login\" => \"sessions#new\" get \"signup\" => \"users#new\" get \"logout\" => \"sessions#destroy\" get \"forgot_password\" => \"password_resets#forgot_password\" post \"forgot_password\" => \"password_resets#send_forgot_password\" get \"password_resets\" => \"password_resets#confirm_token\" post \"password_resets\" => \"password_resets#reset_password\" get \"dashboard/doc\" => \"dashboard#doc\" resources :sessions') == [HttpRoute(url_pattern='/login', method='GET'),
 HttpRoute(url_pattern='/signup', method='GET'),
 HttpRoute(url_pattern='/logout', method='GET'),
 HttpRoute(url_pattern='/forgot_password', method='GET'),
 HttpRoute(url_pattern='/forgot_password', method='POST'),
 HttpRoute(url_pattern='/password_resets', method='GET'),
 HttpRoute(url_pattern='/password_resets', method='POST'),
 HttpRoute(url_pattern='/dashboard/doc', method='GET'),
 HttpRoute(url_pattern='/sessions', method='GET'),
 HttpRoute(url_pattern='/sessions/new', method='GET'),
 HttpRoute(url_pattern='/sessions', method='POST'),
 HttpRoute(url_pattern='/sessions/{id}', method='GET'),
 HttpRoute(url_pattern='/sessions/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/sessions/{id}', method='PUT'),
 HttpRoute(url_pattern='/sessions/{id}', method='DELETE')]


def test_code_to_routes_resources():
    assert code_to_routes(
        'resources :users do get \"account_settings\" resources :retirement resources :paid_time_off resources :work_info resources :performance resources :benefit_forms resources :messages resources :pay do collection do post \"update_dd_info\" post \"decrypted_bank_acct_num\" end end end') == [
               HttpRoute(url_pattern='/users/account_settings', method='GET'),
               HttpRoute(url_pattern='/users/retirement', method='GET'),
               HttpRoute(url_pattern='/users/retirement/new', method='GET'),
               HttpRoute(url_pattern='/users/retirement', method='POST'),
               HttpRoute(url_pattern='/users/retirement/{id}', method='GET'),
               HttpRoute(url_pattern='/users/retirement/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/users/retirement/{id}', method='PUT'),
               HttpRoute(url_pattern='/users/retirement/{id}', method='DELETE'),
               HttpRoute(url_pattern='/users/paid_time_off', method='GET'),
               HttpRoute(url_pattern='/users/paid_time_off/new', method='GET'),
               HttpRoute(url_pattern='/users/paid_time_off', method='POST'),
               HttpRoute(url_pattern='/users/paid_time_off/{id}', method='GET'),
               HttpRoute(url_pattern='/users/paid_time_off/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/users/paid_time_off/{id}', method='PUT'),
               HttpRoute(url_pattern='/users/paid_time_off/{id}', method='DELETE'),
               HttpRoute(url_pattern='/users/work_info', method='GET'),
               HttpRoute(url_pattern='/users/work_info/new', method='GET'),
               HttpRoute(url_pattern='/users/work_info', method='POST'),
               HttpRoute(url_pattern='/users/work_info/{id}', method='GET'),
               HttpRoute(url_pattern='/users/work_info/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/users/work_info/{id}', method='PUT'),
               HttpRoute(url_pattern='/users/work_info/{id}', method='DELETE'),
               HttpRoute(url_pattern='/users/performance', method='GET'),
               HttpRoute(url_pattern='/users/performance/new', method='GET'),
               HttpRoute(url_pattern='/users/performance', method='POST'),
               HttpRoute(url_pattern='/users/performance/{id}', method='GET'),
               HttpRoute(url_pattern='/users/performance/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/users/performance/{id}', method='PUT'),
               HttpRoute(url_pattern='/users/performance/{id}', method='DELETE'),
               HttpRoute(url_pattern='/users/benefit_forms', method='GET'),
               HttpRoute(url_pattern='/users/benefit_forms/new', method='GET'),
               HttpRoute(url_pattern='/users/benefit_forms', method='POST'),
               HttpRoute(url_pattern='/users/benefit_forms/{id}', method='GET'),
               HttpRoute(url_pattern='/users/benefit_forms/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/users/benefit_forms/{id}', method='PUT'),
               HttpRoute(url_pattern='/users/benefit_forms/{id}', method='DELETE'),
               HttpRoute(url_pattern='/users/messages', method='GET'),
               HttpRoute(url_pattern='/users/messages/new', method='GET'),
               HttpRoute(url_pattern='/users/messages', method='POST'),
               HttpRoute(url_pattern='/users/messages/{id}', method='GET'),
               HttpRoute(url_pattern='/users/messages/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/users/messages/{id}', method='PUT'),
               HttpRoute(url_pattern='/users/messages/{id}', method='DELETE'),
               HttpRoute(url_pattern='/users/pay/update_dd_info', method='POST'),
               HttpRoute(url_pattern='/users/pay/decrypted_bank_acct_num', method='POST')]
    assert code_to_routes('resources :tutorials do collection do get \"credentials\" end end') == [
 HttpRoute(url_pattern='/tutorials/credentials', method='GET')]
    assert code_to_routes('resources :schedule do collection do get \"get_pto_schedule\" end end') == [
 HttpRoute(url_pattern='/schedule/get_pto_schedule', method='GET')]
    assert code_to_routes(
        'resources :admin do get \"dashboard\" get \"get_user\" post \"delete_user\" patch \"update_user\" get \"get_all_users\" get \"analytics\" end') == [
 HttpRoute(url_pattern='/admin/dashboard', method='GET'),
 HttpRoute(url_pattern='/admin/get_user', method='GET'),
 HttpRoute(url_pattern='/admin/delete_user', method='POST'),
 HttpRoute(url_pattern='/admin/{id}/update_user', method='PUT'),
 HttpRoute(url_pattern='/admin/get_all_users', method='GET'),
 HttpRoute(url_pattern='/admin/analytics', method='GET')]


def test_code_to_routes_sidekiq():
    assert code_to_routes("""namespace \"admin\" do #load Sidekiq web UI if IS_SIDEKIQ || IS_SIDEKIQ_COMMERCE || IS_SIDEKIQ_ENTITY_RECOMMENDER || IS_SIDEKIQ_AUCTION mount Sidekiq::Web, :at => '/sidekiq', :constraints => AdminHelper::AdminHttpBasicAuth.new end scope \"templates\", :controller => 'email_templates' do get 'edit', :action => 'edit', :as => 'email_template_edit' end resources :target_tag_groups resources :email_templates resources :email_triggers do get 'show_changelog', controller: 'email_triggers', action: 'show_changelog', as: 'show_changelog' end resources :retail_brand_mappings get '/user_development_notifications', :to => 'user_development_notifications#list_udns', :as => 'user_development_notifications' get '/marketing_campaign_scheduler', :to => 'admin_marketing_campaign#marketing_campaign_scheduler', :as => 'marketing_campaign_scheduler' post '/schedule_marketing_campaign', :to => 'admin_marketing_campaign#schedule_marketing_campaign', :as => 'schedule_marketing_campaign' match \"batch_push_sche...""") == [HttpRoute(url_pattern='/admin/sidekiq', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/busy', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/queues', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/queues/{name}', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/queues/{name}', method='POST'),
 HttpRoute(url_pattern='/admin/sidekiq/retries', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/retries/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/retries/{id}', method='POST'),
 HttpRoute(url_pattern='/admin/sidekiq/retries/all/delete', method='POST'),
 HttpRoute(url_pattern='/admin/sidekiq/retries/all/retry', method='POST'),
 HttpRoute(url_pattern='/admin/sidekiq/scheduled', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/scheduled/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/sidekiq/scheduled/{id}', method='POST'),
 HttpRoute(url_pattern='/admin/sidekiq/scheduled/all', method='POST'),
 HttpRoute(url_pattern='/admin/templates/edit', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups/new', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups', method='POST'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}', method='PUT'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}', method='DELETE'),
 HttpRoute(url_pattern='/admin/email_templates', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates/new', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates', method='POST'),
 HttpRoute(url_pattern='/admin/email_templates/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates/{id}', method='PUT'),
 HttpRoute(url_pattern='/admin/email_templates/{id}', method='DELETE'),
 HttpRoute(url_pattern='/admin/email_triggers/show_changelog', method='GET'),
 HttpRoute(url_pattern='/admin/retail_brand_mappings/new', method='GET'),
 HttpRoute(url_pattern='/admin/retail_brand_mappings', method='POST'),
 HttpRoute(url_pattern='/admin/retail_brand_mappings/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/retail_brand_mappings/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/admin/retail_brand_mappings/{id}', method='PUT'),
 HttpRoute(url_pattern='/admin/retail_brand_mappings/{id}', method='DELETE'),
 HttpRoute(url_pattern='/admin/user_development_notifications',
           method='GET'),
 HttpRoute(url_pattern='/admin/marketing_campaign_scheduler',
           method='GET'),
 HttpRoute(url_pattern='/admin/schedule_marketing_campaign',
           method='POST'),
HttpRoute(url_pattern='/admin/batch_push_sche', method='GET')]

def test_code_to_routes_scope_dangling():
    assert code_to_routes("""resources :consignment_requests, only: [:show] do member do get :print put 'state', to: :update_state, as: :update_state end end""") == [HttpRoute(url_pattern='/consignment_requests/{print}', method='GET'),
 HttpRoute(url_pattern='/consignment_requests/{id}/state', method='PUT')]
    # Needs development
    assert code_to_routes("""scope \"payments_gift_card_infos\", :controller => \"admin_payments_gift_card_infos\" do match \"(:gift_card_fingerprint)""") == [HttpRoute(url_pattern='/payments_gift_card_infos/{gift_card_fingerprint}',
           method='GET')]
    assert code_to_routes("""scope \"payments_upi_infos\", :controller => \"admin_payments_upi_infos\" do match \"(:upi_info_id)""") == [HttpRoute(url_pattern='/payments_upi_infos/{upi_info_id}', method='GET')]
    assert code_to_routes("""scope \"payments_venmo_infos\", :controller => \"admin_payments_venmo_infos\" do match \"(:venmo_info_id)""") == [HttpRoute(url_pattern='/payments_venmo_infos/{venmo_info_id}', method='GET')]
    assert code_to_routes("""scope \"payments_apple_pay_infos\", :controller => \"admin_payments_apple_pay_infos\" do match \"(:apple_pay_info_id)""") == [HttpRoute(url_pattern='/payments_apple_pay_infos/{apple_pay_info_id}',
           method='GET')]
    assert code_to_routes("""scope 'offers/(:offer_id)""") == []
    assert code_to_routes("""scope \"/referral_codes/(:referral_code)""") == []
    assert code_to_routes("""scope 'brands', :controller=>'admin_brands' do get 'list_brands', :action=>'list_brands', :as=>'list_brands' get 'add_brand_form', :action=>'add_brand_form', :as=>'add_brand_form' get 'add_synonym_form', :action=>'add_synonym_form', :as=>'add_synonym_form' post 'recent_brands', :action=>'recent_brands', :as=>'recent_brands' post 'add_brand', :action =>'add_brand', :as=>'add_brand' post 'add_synonym', :action =>'add_synonym', :as=>'add_synonym' get ':brand_id/brand_details', :action =>'brand_details', :as=>'brand_details' post ':brand_id/promoted_user', :action => 'update_promoted_user', :as => 'update_promoted_user' post 'find_brand', :action => 'find_brand', :as => 'find_brand' end""") == [HttpRoute(url_pattern='/brands/list_brands', method='GET'),
 HttpRoute(url_pattern='/brands/add_brand_form', method='GET'),
 HttpRoute(url_pattern='/brands/add_synonym_form', method='GET'),
 HttpRoute(url_pattern='/brands/recent_brands', method='POST'),
 HttpRoute(url_pattern='/brands/add_brand', method='POST'),
 HttpRoute(url_pattern='/brands/add_synonym', method='POST'),
 HttpRoute(url_pattern='/brands/{brand_id}/brand_details', method='GET'),
 HttpRoute(url_pattern='/brands/{brand_id}/promoted_user', method='POST'),
 HttpRoute(url_pattern='/brands/find_brand', method='POST')]
    assert code_to_routes("""scope 'influencer_campaigns', :controller => 'admin_influencer_program_campaigns' do get 'list_jobs', :action => 'list_jobs', :as => 'list_jobs' post 'download_jobs', :action => 'download_jobs', :as => 'download_jobs' end""") == [HttpRoute(url_pattern='/influencer_campaigns/list_jobs', method='GET'),
 HttpRoute(url_pattern='/influencer_campaigns/download_jobs', method='POST')]
    assert code_to_routes("""scope 'users/(:user_id)""") == []
    assert code_to_routes("""scope 'bulk_account_actions' do get 'summary', :action => 'bulk_account_actions_summary', :as => 'bulk_account_actions_summary' match 'new', :action => 'new_bulk_account_action', :as => 'ne
w_bulk_account_action', :via => [:get, :post] end""") == [HttpRoute(url_pattern='/bulk_account_actions/summary', method='GET'),
 HttpRoute(url_pattern='/bulk_account_actions/new', method='GET')]
    assert code_to_routes("""scope \"templates\", :controller => 'email_templates' do get 'edit', :action => 'edit', :as => 'email_template_edit' end""") == [HttpRoute(url_pattern='/templates/edit', method='GET')]
    assert code_to_routes("""member do get :print put 'state', to: :update_state, as: :update_state end""") == [HttpRoute(url_pattern='/{print}', method='GET'), HttpRoute(url_pattern='/{id}/state', method='PUT')]
    assert code_to_routes("""scope \"posts/(:post_id)""") == []
    assert code_to_routes("""resources :email_triggers do get 'show_changelog', controller: 'email_triggers', action: 'show_changelog', as: 'show_changelog' end""") == [HttpRoute(url_pattern='/email_triggers', method='GET'),
 HttpRoute(url_pattern='/email_triggers/new', method='GET'),
 HttpRoute(url_pattern='/email_triggers', method='POST'),
 HttpRoute(url_pattern='/email_triggers/{id}', method='GET'),
 HttpRoute(url_pattern='/email_triggers/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/email_triggers/{id}', method='PATCH'),
 HttpRoute(url_pattern='/email_triggers/{id}/destroy', method='DELETE'),
 HttpRoute(url_pattern='/show_changelog', method='GET')]
    assert code_to_routes("""scope \"reports\", :controller => \"admin_user\" do post \"approve_report\" , :action => 'submit_approve_report', :as => 'submit_approve_report' post \"ignore_report\" , :action => 'submit_ignore_report', :as => 'submit_ignore_report' end""") == [HttpRoute(url_pattern='/reports/approve_report', method='POST'),
 HttpRoute(url_pattern='/reports/ignore_report', method='POST')]
    assert code_to_routes("""scope :controller => \"admin_experiences\" do get 'markets', :action => 'list_experiences', :as => 'list_experiences' get 'markets/:short_name', :action => 'admin_view_experience', :as => '
view_experience' post 'markets/:short_name', :action => 'admin_update_experience', :as => 'update_experience' get 'markets/:short_name/web_nav', :action => 'market_web_nav_config', :as => 'market_web_nav_config' post 'mark
ets/:short_name/web_nav', :action => 'market_web_nav_config', :as => 'update_market_web_nav_config' get 'markets/web_nav/get_showrooms', :action => 'get_showrooms_for_nav', :as => 'get_showrooms_for_nav' end""") == [HttpRoute(url_pattern='/markets', method='GET'),
 HttpRoute(url_pattern='/markets/{short_name}', method='GET'),
 HttpRoute(url_pattern='/markets/{short_name}', method='POST'),
 HttpRoute(url_pattern='/markets/{short_name}/web_nav',
           method='GET'),
 HttpRoute(url_pattern='/mark', method='POST'),
 HttpRoute(url_pattern='/markets/web_nav/get_showrooms',
           method='GET')]
    assert code_to_routes("""scope :controller => \"admin_feature_settings\" do get \"list_feature_settings\", :action => 'list_feature_settings', :as => 'list_feature_settings' get \"editable_feature_settings\", :acti
on => 'list_feature_settings', :as => 'editable_feature_settings', :editable => true get \"deprecated_feature_settings\", :action => 'list_feature_settings', :as => 'deprecated_feature_settings', :deprecated => true get \"
list_mapping_overrides\", :action => 'list_mapping_overrides', :as => 'list_mapping_overrides' post \"reset_mapping_overrides\", :action => 'feature_settings', :as => 'reset_mapping_overrides' get \"my_feature_settings\",
:action => 'list_feature_settings', :as => 'my_feature_settings', :my => true match \"feature_settings/:feature_id\", :action => 'feature_settings', :as => 'feature_settings', :via => [:get, :post] match \"feature_settings
/:feature_id/variations_list\", :action => 'list_variations', :as => 'variations_list', :via => [:get, :post] get 'feature_settings/:feature_id/show_mappings_hi...""") == [HttpRoute(url_pattern='/list_feature_settings', method='GET'),
 HttpRoute(url_pattern='/editable_feature_settings', method='GET'),
 HttpRoute(url_pattern='/deprecated_feature_settings', method='GET'),
 HttpRoute(url_pattern='/', method='GET'),
 HttpRoute(url_pattern='/reset_mapping_overrides', method='POST'),
 HttpRoute(url_pattern='/my_feature_settings', method='GET'),
 HttpRoute(url_pattern='/feature_settings/{feature_id}', method='GET'),
 HttpRoute(url_pattern='/feature_settings', method='GET'),
 HttpRoute(url_pattern='/feature_settings/{feature_id}/show_mappings_hi',
           method='GET')]
    assert code_to_routes("""scope :controller => 'admin_service_flags' do get 'list_service_flags', :action => 'list_service_flags', :as => 'list_service_flags' end""") == [HttpRoute(url_pattern='/list_service_flags', method='GET')]

def test_code_to_routes_scope_multiple_path():
    assert code_to_routes("""scope \"inventory_unit/:inventory_unit_id\" do post \"clear_inventory_unit\" post \"received_inventory_unit\" post \"send_shipping_reminder\" post \"send_final_shipping_reminder\" post \"return_shipping_reminder\" post \"send_cancel_order_notice\" post \"send_buyer_shipping_delayed\" post \"send_buyer_shipping_really_delayed\" post \"send_concierge_delayed\" post \"shipped_inventory_unit\" post \"item_shipped_email\" post \"buyer_accept_order_reminder_email\" post \"delivered_inventory_unit\" post \"concierge_delivered_inventory_unit\" post \"concierge_shipped_inventory_unit\" post \"return_shipped_inventory_unit\" post \"item_delivered_email\" post \"send_notice_left\" post \"order_not_delivered\" end""") == [HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/clear_inventory_unit',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/received_inventory_unit',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/send_shipping_reminder',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/send_final_shipping_reminder',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/return_shipping_reminder',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/send_cancel_order_notice',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/send_buyer_shipping_delayed',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/send_buyer_shipping_really_delayed',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/send_concierge_delayed',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/shipped_inventory_unit',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/item_shipped_email',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/buyer_accept_order_reminder_email',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/delivered_inventory_unit',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/concierge_delivered_inventory_unit',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/concierge_shipped_inventory_unit',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/return_shipped_inventory_unit',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/item_delivered_email',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/send_notice_left',
           method='POST'),
 HttpRoute(url_pattern='/inventory_unit/{inventory_unit_id}/order_not_delivered',
           method='POST')]
    assert code_to_routes("""scope \"payments_card_infos\", :controller=> \"admin_payments_card_infos\" do match \"(:card_info_id)""") == [HttpRoute(url_pattern='/payments_card_infos/{card_info_id}', method='GET')]
    assert code_to_routes("""scope \"payments_paypal_infos\", :controller => \"admin_payments_paypal_infos\" do match \"(:paypal_info_id)""") == [HttpRoute(url_pattern='/payments_paypal_infos/{paypal_info_id}', method='GET')]
    assert code_to_routes("""scope :controller=>'search_v2' do get 'brand/:brand', :action => 'listings_by_brand', :as => 'search_by_brand', :constraints => {:brand => /[^//]+/} # MOVED TO NODE, Still referenced
by Rails application helper end""") == [HttpRoute(url_pattern='/brand/{brand}', method='GET')]
    assert code_to_routes("""scope :controller=>'bundle_v3' do get '/bundles/:bundle_id', :action => 'get_bundle_v3', :as => 'bundle_v3_id'""") == [HttpRoute(url_pattern='/bundles/{bundle_id}', method='GET')]


def test_code_to_routes_collection():
    assert code_to_routes('collection do post \"update_dd_info\" post \"decrypted_bank_acct_num\" end') == [
        HttpRoute(url_pattern='/update_dd_info', method='POST'),
        HttpRoute(url_pattern='/decrypted_bank_acct_num', method='POST')]
    assert code_to_routes('collection do get \"credentials\" end') == [
        HttpRoute(url_pattern='/credentials', method='GET')]


def test_code_to_routes_namespace():
    assert code_to_routes(
        'namespace :api, defaults: {format: \"json\"} do namespace :v1 do resources :users resources :mobile end end') == [
               HttpRoute(url_pattern='/api/v1/users', method='GET'),
               HttpRoute(url_pattern='/api/v1/users/new', method='GET'),
               HttpRoute(url_pattern='/api/v1/users', method='POST'),
               HttpRoute(url_pattern='/api/v1/users/{id}', method='GET'),
               HttpRoute(url_pattern='/api/v1/users/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/api/v1/users/{id}', method='PUT'),
               HttpRoute(url_pattern='/api/v1/users/{id}', method='DELETE')]

    assert code_to_routes('namespace :v1 do resources :users resources :mobile end') == [
        HttpRoute(url_pattern='/v1/users', method='GET'),
        HttpRoute(url_pattern='/v1/users/new', method='GET'),
        HttpRoute(url_pattern='/v1/users', method='POST'),
        HttpRoute(url_pattern='/v1/users/{id}', method='GET'),
        HttpRoute(url_pattern='/v1/users/{id}/edit', method='GET'),
        HttpRoute(url_pattern='/v1/users/{id}', method='PUT'),
        HttpRoute(url_pattern='/v1/users/{id}', method='DELETE')]


def test_code_to_routes_advanced():
    assert code_to_routes("scope :controller=>'search_v2' do get 'brand/:brand', :action => 'listings_by_brand', :as => 'search_by_brand', :constraints => {:brand => /[^//]+/}") == [HttpRoute(url_pattern='/brand/{brand}', method='GET')]
    assert code_to_routes("def resource (...)") == []
    assert code_to_routes('resources :photos do member do get "preview" end end') == [HttpRoute(url_pattern='/photos', method='GET'),
 HttpRoute(url_pattern='/photos/new', method='GET'),
 HttpRoute(url_pattern='/photos', method='POST'),
 HttpRoute(url_pattern='/photos/{id}', method='GET'),
 HttpRoute(url_pattern='/photos/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/photos/{id}', method='PATCH'),
 HttpRoute(url_pattern='/photos/{id}/destroy', method='DELETE'),
 HttpRoute(url_pattern='/photos/{id}/preview', method='GET'),
 HttpRoute(url_pattern='/preview', method='GET')]
    assert code_to_routes('get "こんにちは", to: "welcome#index"') == [
        HttpRoute(url_pattern='/こんにちは', method='GET')]
    assert code_to_routes(
        'scope ":account_id", as: "account", constraints: { account_id: /\\d+/ } do resources :articles end') == [HttpRoute(url_pattern='/{account_id}/articles', method='GET'),
 HttpRoute(url_pattern='/{account_id}/articles/new', method='GET'),
 HttpRoute(url_pattern='/{account_id}/articles', method='POST'),
 HttpRoute(url_pattern='/{account_id}/articles/{id}', method='GET'),
 HttpRoute(url_pattern='/{account_id}/articles/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/{account_id}/articles/{id}', method='PATCH'),
 HttpRoute(url_pattern='/{account_id}/articles/{id}/destroy', method='DELETE')]
    assert code_to_routes(
        'scope(path_names: { new: "neu", edit: "bearbeiten" }) do resources :categories, path: "kategorien" end') == [
               HttpRoute(url_pattern='/kategorien', method='GET'),
               HttpRoute(url_pattern='/kategorien/neu', method='GET'),
               HttpRoute(url_pattern='/kategorien', method='POST'),
               HttpRoute(url_pattern='/kategorien/{id}', method='GET'),
               HttpRoute(url_pattern='/kategorien/{id}/bearbeiten', method='GET'),
               HttpRoute(url_pattern='/kategorien/{id}', method='PATCH'),
               HttpRoute(url_pattern='/kategorien/{id}/destroy', method='DELETE')]

def test_code_to_routes_large():
    assert code_to_routes('match "list_swap_orders", :action => "list_swap_orders", :via => [:get, :post]') == [HttpRoute(url_pattern='/list_swap_orders', method='GET'),
 HttpRoute(url_pattern='/list_swap_orders', method='POST')]
    assert code_to_routes("""Web::Application.routes.draw do
        namespace "admin"  do
        scope "templates", :controller => 'email_templates' do
          get 'edit', :action => 'edit', :as => 'email_template_edit'
        end
    
        resources :target_tag_groups
        resources :email_templates
        resources :fashion_term_keywords
        resources :fashion_term_summaries
        scope "swap_order/(:swap_order_id)" , :controller=>"admin_order" do
          get "view_swap_order", :action => "view_swap_order", :as => 'view_swap_order'
          post "buyer_swap_order_reminder", :action =>"buyer_swap_order_reminder", :as =>"buyer_swap_order_reminder"
          match "list_swap_orders", :action => "list_swap_orders", :via => [:get, :post]
        end
        scope 'users/(:user_id)', :constraints => { :user_id => /[^\/]+/ }, :controller => 'admin_user' do
          get "list_users"
          get "view_user"
        end
    end
end""") == [HttpRoute(url_pattern='/admin/templates/edit', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups/new', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups', method='POST'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}', method='PUT'),
 HttpRoute(url_pattern='/admin/target_tag_groups/{id}', method='DELETE'),
 HttpRoute(url_pattern='/admin/email_templates', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates/new', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates', method='POST'),
 HttpRoute(url_pattern='/admin/email_templates/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/admin/email_templates/{id}', method='PUT'),
 HttpRoute(url_pattern='/admin/email_templates/{id}', method='DELETE'),
 HttpRoute(url_pattern='/admin/fashion_term_keywords', method='GET'),
 HttpRoute(url_pattern='/admin/fashion_term_keywords/new', method='GET'),
 HttpRoute(url_pattern='/admin/fashion_term_keywords', method='POST'),
 HttpRoute(url_pattern='/admin/fashion_term_keywords/{id}', method='GET'),
 HttpRoute(url_pattern='/admin/fashion_term_keywords/{id}/edit', method='GET'),
 HttpRoute(url_pattern='/admin/fashion_term_keywords/{id}', method='PUT'),
 HttpRoute(url_pattern='/admin/fashion_term_keywords/{id}', method='DELETE'),
 HttpRoute(url_pattern='/admin/swap_order/{swap_order_id}/view_swap_order',
           method='GET'),
 HttpRoute(url_pattern='/admin/swap_order/{swap_order_id}/buyer_swap_order_reminder',
           method='POST'),
HttpRoute(url_pattern='/admin/swap_order/{swap_order_id}/list_swap_orders',
           method='GET'),
 HttpRoute(url_pattern='/admin/users/{user_id}/list_users', method='GET'),
 HttpRoute(url_pattern='/admin/users/{user_id}/view_user', method='GET')]

def test_code_to_routes_sinatra():
    assert fix_url_params('/download/*.*') == "/download/{extra_path}"
    assert code_to_routes("get '/' do Sinatra::RestApi::Router.list_routes.to_json end") == [
        HttpRoute(url_pattern='/', method='GET')]
    assert code_to_routes("get '/' do @details = OpenStruct.new( attributes: {} )") == [
        HttpRoute(url_pattern='/', method='GET')]
    assert code_to_routes("get '/:model' do mod = @models[params[:model].to_sym] @model = mod.to_s.split( '::' )") == [
        HttpRoute(url_pattern='/{model}', method='GET')]
    assert code_to_routes("get '/:model/:id' do mod = @models[params[:model].to_sym] @details = mod.find( params[:id] )") == [
        HttpRoute(url_pattern='/{model}/{id}', method='GET')]
    assert code_to_routes("get '/:model/:id/delete' do @item = @models[params[:model].to_sym].find( params[:id] )") == [
        HttpRoute(url_pattern='/{model}/{id}/delete', method='GET')]
    assert code_to_routes("options '*' do response.headers['Access-Control-Allow-Origin'] = '*' response.headers['Access-Control-Allow-Methods'] = 'HEAD,GET,PUT,DELETE,OPTIONS' response.headers['Access-Control-Allow-Headers'] = 'X-Requested-With, X-HTTP-Method-Override, Content-Type, Cache-Control, Accept' halt 200 end") == [
        HttpRoute(url_pattern='/', method='OPTIONS')]
    assert code_to_routes("post '/:model/:id' do mod = @models[params[:model].to_sym] @details = mod.find( params[:id] )") == [
        HttpRoute(url_pattern='/{model}/{id}', method='POST')]
    assert code_to_routes("post '/:model' do mod = @models[params[:model].to_sym] @model = mod.to_s.split( '::' )") == [
        HttpRoute(url_pattern='/{model}', method='POST')]
    assert code_to_routes("get '/download/*.*' do") == [
        HttpRoute(url_pattern='/download/{extra_path}', method='GET')]
    # These two patterns are not supported by swagger, so needs some post-processing
    assert code_to_routes("get '/hello/([\\w]+)/' do") == [
        HttpRoute(url_pattern='/hello/([\\w]+)', method='GET')]
    assert code_to_routes("get '%r{/hello/([\\w]+)}' do") == [
        HttpRoute(url_pattern='/%r{/hello/([\\w]+)}', method='GET')]

