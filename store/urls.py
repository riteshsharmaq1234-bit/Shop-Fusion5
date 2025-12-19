from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView, LoginView
from .views import custom_logout
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/public-home/', permanent=False)),
    path('public-home/', views.home, name='home'),
    path('category/<str:category_name>/', views.product_list, name='product_list'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart, name='cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart-item/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('track-order/', views.track_order, name='track_order'),
    path('login/', views.StoreLoginView.as_view(), name='login'),
    path('signup/', views.signup, name='signup'),
    path('home/', views.user_home, name='user_home'),
    path('logout/', custom_logout, name='logout'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('profile/', views.profile, name='user_profile'),

    # Delivery partner URLs
    path('delivery-partner/signup/', views.delivery_signup, name='delivery_partner_signup'),
    path('delivery-partner/login/', views.delivery_partner_login, name='delivery_partner_login'),
    path('delivery-partner/dashboard/', views.delivery_dashboard, name='delivery_dashboard'),
    path('delivery-partner/order/<int:order_id>/', views.delivery_order_detail, name='delivery_order_detail'),
    path('delivery-partner/logout/', views.delivery_partner_logout, name='delivery_partner_logout'),
    path('about/', views.about, name='about_us'),
    path('support/', views.support, name='support'),
    # Wishlist
    path('wishlist/', views.wishlist_page, name='wishlist_page'),
    path('api/wishlist/', views.wishlist_api, name='wishlist_api'),
    path('api/wishlist/status/', views.wishlist_status, name='wishlist_status'),
    path('api/wishlist/add/', views.wishlist_add, name='wishlist_add'),
    path('api/wishlist/remove/', views.wishlist_remove, name='wishlist_remove'),
    path('api/wishlist/move-to-cart/', views.wishlist_move_to_cart, name='wishlist_move_to_cart'),
    path('api/wishlist/guest/', views.wishlist_guest_save, name='wishlist_guest_save'),
    path('save-for-later/', views.save_for_later, name='save_for_later'),
    
    # Aliases for common order URLs to prevent 404s
    path('orders/', views.my_orders, name='orders'),
    path('order/', RedirectView.as_view(url='/my-orders/', permanent=False)),
]
