import pytest
from atom_tools.lib import HttpRoute
from atom_tools.lib.ruby_semantics import code_to_routes, fix_url_params


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


def test_code_to_routes_dangling():
    assert code_to_routes(
        'Railsgoat::Application.routes.draw do get \"login\" => \"sessions#new\" get \"signup\" => \"users#new\" get \"logout\" => \"sessions#destroy\" get \"forgot_password\" => \"password_resets#forgot_password\" post \"forgot_password\" => \"password_resets#send_forgot_password\" get \"password_resets\" => \"password_resets#confirm_token\" post \"password_resets\" => \"password_resets#reset_password\" get \"dashboard/doc\" => \"dashboard#doc\" resources :sessions') == [
               HttpRoute(url_pattern='/login', method='GET'),
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
               HttpRoute(url_pattern='/admin/update_user', method='PUT'),
               HttpRoute(url_pattern='/admin/get_all_users', method='GET'),
               HttpRoute(url_pattern='/admin/analytics', method='GET')]


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
    assert code_to_routes('resources :photos do member do get "preview" end end') == [
        HttpRoute(url_pattern='/photos/preview', method='GET')]
    assert code_to_routes('get "こんにちは", to: "welcome#index"') == [
        HttpRoute(url_pattern='/こんにちは,', method='GET')]
    assert code_to_routes(
        'scope ":account_id", as: "account", constraints: { account_id: /\d+/ } do resources :articles end') == [
               HttpRoute(url_pattern='/account_id/articles', method='GET'),
               HttpRoute(url_pattern='/account_id/articles/new', method='GET'),
               HttpRoute(url_pattern='/account_id/articles', method='POST'),
               HttpRoute(url_pattern='/account_id/articles/{id}', method='GET'),
               HttpRoute(url_pattern='/account_id/articles/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/account_id/articles/{id}', method='PUT'),
               HttpRoute(url_pattern='/account_id/articles/{id}', method='DELETE')]
    assert code_to_routes(
        'scope(path_names: { new: "neu", edit: "bearbeiten" }) do resources :categories, path: "kategorien" end') == [
               HttpRoute(url_pattern='/kategorien/categories', method='GET'),
               HttpRoute(url_pattern='/kategorien/categories/new', method='GET'),
               HttpRoute(url_pattern='/kategorien/categories', method='POST'),
               HttpRoute(url_pattern='/kategorien/categories/{id}', method='GET'),
               HttpRoute(url_pattern='/kategorien/categories/{id}/edit', method='GET'),
               HttpRoute(url_pattern='/kategorien/categories/{id}', method='PUT'),
               HttpRoute(url_pattern='/kategorien/categories/{id}', method='DELETE')]


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
    assert code_to_routes("get '/hello/([\w]+)/' do") == [
        HttpRoute(url_pattern='/hello/([\w]+)/', method='GET')]
    assert code_to_routes("get '%r{/hello/([\w]+)}' do") == [
        HttpRoute(url_pattern='/%r{/hello/([\\w]+)}', method='GET')]
