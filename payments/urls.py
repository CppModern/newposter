from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path("permit/", views.permit_group),
    path("post/", views.add_post),
    path("addorder/", views.add_order),
    path("orders/<user_id>/", views.get_orders),
    path("posts/<duration>/", views.get_posts),
    path("post/<post_id>/", views.get_post),
    path("userposts/<user_id>/", views.getuser_posts),
    path("addgroup/", views.add_group),
    path("deletegroup/", views.delete_group),
    path("deletepost/", views.delete_posts),
    path("promote/", views.promote_user),
    path("groups/", views.get_groups),
    path("update_last/", views.update_user_last),
    path("groups/<user_id>/", views.get_user_groups),
    path('', views.home, name='home'),
    path('create/', views.create_payment, name='create_payment'),
    path('invoice/<pk>/', views.track_invoice, name='track_payment'),
    path('receive/', views.receive_payment, name='receive_payment'),
    path("users/", views.get_users, name="users"),
    path("users/banned/", views.get_banned_users),
    path("user/<pk>/", views.get_user, name="user"),
    path("createuser/", views.create_user),
    path("products/", views.get_products),
    path("product/<pk>/", views.get_product),
    path("invoices/", views.get_invoices),
    path("invoice/<pk>/", views.get_invoice),
    path("ban/", views.ban_user),
    path("unban/", views.unban_user),
    path("balance/", views.update_user_balance),
    path("deleteproduct/", views.delete_product),
    path("createproduct/", views.create_product),
    path("updateproduct/", views.update_product),
    path("usersdump/", views.users_dump),
    path("createorder/", views.create_order),
    path("pendingorders/<user_id>/", views.pending_users_orders),
    path("settledorders/<user_id>/", views.settled_users_orders),
    path("approveorders/", views.approve_order),
    path("transactiontoday/", views.transactions_today),
    path("transactionweekly/", views.transactions_weekly),
    path("transactionmonthly/", views.transactions_monthly),
    path("transactionall/", views.transactions_all)
]

