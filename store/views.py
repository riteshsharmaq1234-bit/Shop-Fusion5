
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import LoginView
from django.contrib.auth import login, logout # Ensure logout is imported here

from django.contrib.auth.hashers import check_password
from django.views.decorators.csrf import csrf_protect

# Delivery partner logout view
def delivery_partner_logout(request):
    request.session.flush()
    return redirect('delivery_partner_login')

# Custom login view for delivery partner (authenticates against DeliveryPartnerUser only)
@csrf_protect
def delivery_partner_login(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        # Prevent regular users from logging in as delivery partners
        from django.contrib.auth.models import User
        if User.objects.filter(username=username).exists():
            error = 'This is a regular user account. Please use the user login.'
        else:
            try:
                partner = DeliveryPartnerUser.objects.get(username=username)
                if check_password(password, partner.password):
                    request.session['delivery_partner_authenticated'] = True
                    request.session['delivery_partner_username'] = partner.username
                    return redirect('delivery_dashboard')
                else:
                    error = 'Invalid credentials.'
            except DeliveryPartnerUser.DoesNotExist:
                error = 'Invalid credentials.'
    return render(request, 'store/delivery_login.html', {'error': error})
    def get_success_url(self):
        return '/delivery-partner/dashboard/'
from .models import DeliveryPartnerUser, Category, Product, CartItem, Address, Order, SupportRequest
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core import serializers
import json
from .models import Wishlist
from django import forms

# Delivery partner order detail view (uses delivery partner session auth)
def delivery_order_detail(request, order_id):
    # Use delivery partner session flag for auth (separate DeliveryPartnerUser model)
    if not request.session.get('delivery_partner_authenticated'):
        return redirect('delivery_partner_login')
    order = Order.objects.select_related('user', 'address').prefetch_related('items__product').filter(id=order_id).first()
    if not order:
        return HttpResponse('Order not found.', status=404)
    return render(request, 'store/delivery_order_detail.html', {'order': order})


# Custom form for DeliveryPartnerUser signup
class DeliveryPartnerSignupForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    class Meta:
        model = DeliveryPartnerUser
        fields = ['username', 'password', 'email', 'phone', 'address', 'vehicle_number', 'id_proof']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-control'}),
            'id_proof': forms.TextInput(attrs={'class': 'form-control'}),
        }

# Delivery partner signup view
def delivery_signup(request):
    success = False
    error = None
    SECRET_CODE = 'RITESH'  # Change this to your desired code
    if request.method == 'POST':
        code = request.POST.get('secret_code')
        form = DeliveryPartnerSignupForm(request.POST)
        if code != SECRET_CODE:
            error = 'Invalid secret code.'
        elif form.is_valid():
            partner = form.save(commit=False)
            partner.password = make_password(form.cleaned_data['password'])
            partner.save()
            success = True
        # else: error will be shown by form errors
    else:
        form = DeliveryPartnerSignupForm()
    return render(request, 'store/delivery_signup.html', {'form': form, 'success': success, 'error': error})

# Delivery partner dashboard view (secure: only for delivery partners)
def delivery_dashboard(request):
    # Check if delivery partner is authenticated via session
    if not request.session.get('delivery_partner_authenticated'):
        return redirect('delivery_partner_login')
    # Base queryset
    orders_qs = Order.objects.select_related('user', 'address').prefetch_related('items__product').all()

    # Filters from GET params
    order_id = request.GET.get('order_id') or request.GET.get('q')
    username = request.GET.get('username')
    postal_code = request.GET.get('postal_code')
    date = request.GET.get('date')

    # Filter by order id (exact numeric id)
    if order_id:
        if str(order_id).isdigit():
            orders_qs = orders_qs.filter(id=int(order_id))
        else:
            # no-op if not numeric; could search username or similar instead
            orders_qs = orders_qs.none()

    # Filter by postal code (partial match)
    if postal_code:
        orders_qs = orders_qs.filter(address__postal_code__icontains=postal_code)

    # Filter by username (partial, case-insensitive)
    if username:
        orders_qs = orders_qs.filter(user__username__icontains=username)

    # Filter by a single date (YYYY-MM-DD)
    if date:
        orders_qs = orders_qs.filter(created_at__date=date)

    # Exclude orders that have been marked delivered in the admin.
    # This assumes admins set `tracking_status` to a value containing 'delivered'.
    orders_qs = orders_qs.exclude(tracking_status__icontains='delivered')

    orders = orders_qs.order_by('-created_at')

    # Keep current filter values for form population
    filters = {
        'order_id': order_id or '',
        'username': username or '',
        'postal_code': postal_code or '',
        'date': date or '',
    }

    return render(request, 'store/delivery_dashboard.html', {'orders': orders, 'filters': filters})
from django.contrib.auth.decorators import login_required
# Order detail view
def order_detail(request, order_id):
    shop_user = request.shop_user if getattr(request, 'shop_user', None) else (request.user if request.user.is_authenticated else None)
    if not shop_user:
        return redirect('login')
    order = Order.objects.filter(id=order_id, user=shop_user).select_related('address').prefetch_related('items__product').first()
    if not order:
        return HttpResponse('Order not found or access denied.', status=404)
    return render(request, 'store/order_detail.html', {'order': order})

# My Orders view
def my_orders(request):
    shop_user = request.shop_user if getattr(request, 'shop_user', None) else (request.user if request.user.is_authenticated else None)
    if not shop_user:
        return redirect('login')
    orders = Order.objects.filter(user=shop_user).select_related('address').prefetch_related('items__product').order_by('-created_at')
    return render(request, 'store/my_orders.html', {'orders': orders})
from django.contrib.auth import logout # Ensure logout is imported

# Custom logout view to allow GET requests and redirect to home
from django.shortcuts import redirect
def custom_logout(request):
    # Only clear shop user session keys
    # Also log out Django's authenticated user to keep auth state consistent
    try:
        logout(request)
    except Exception:
        pass
    for key in ['shop_user_authenticated', 'shop_user_id', 'shop_user_username', 'shop_user_email', 'shop_user_date_joined']:
        if key in request.session:
            del request.session[key]
    return redirect('home')
from django.shortcuts import render, get_object_or_404, redirect
from .models import Category, Product, CartItem, Address, Order, OrderItem, SizeStock
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django import forms
from django.http import HttpResponse
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy

# Landing page with categories and featured products

def home(request):
    categories = Category.objects.all()
    return render(request, 'store/home.html', {
        'categories': categories,
    })

# Product list by category

def product_list(request, category_name):
    category = get_object_or_404(Category, name=category_name)
    products = Product.objects.filter(category=category)
    return render(request, 'store/product_list.html', {'category': category, 'products': products})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'store/product_detail.html', {'product': product})

def add_to_cart(request, pk):
    if request.method != 'POST':
        return redirect('product_detail', pk=pk)
    shop_user = request.shop_user if getattr(request, 'shop_user', None) else (request.user if request.user.is_authenticated else None)
    product = get_object_or_404(Product, pk=pk)
    size = request.POST.get('size')
    try:
        qty = int(request.POST.get('quantity', '1'))
    except Exception:
        qty = 1
    if not shop_user:
        request.session['cart_intent'] = {
            'product_id': product.id,
            'size': size,
            'quantity': qty,
        }
        return redirect('login')
    if size not in dict(CartItem.SIZE_CHOICES):
        messages.error(request, 'Please select a valid size.')
        return redirect('product_detail', pk=pk)
    try:
        size_row = SizeStock.objects.get(product=product, size=size)
    except SizeStock.DoesNotExist:
        messages.error(request, 'Size information not available for this product.')
        return redirect('product_detail', pk=pk)
    existing_qty = 0
    existing = CartItem.objects.filter(user=shop_user, product=product, size=size).first()
    if existing:
        existing_qty = existing.quantity
    if size_row.stock < existing_qty + qty:
        messages.error(request, f'Insufficient stock for size {size}. Available: {size_row.stock - existing_qty}')
        return redirect('product_detail', pk=pk)
    cart_item, created = CartItem.objects.get_or_create(user=shop_user, product=product, size=size)
    if not created:
        cart_item.quantity += qty
    else:
        cart_item.quantity = qty
    cart_item.save()
    messages.success(request, 'Added to cart')
    return redirect('cart')

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['address_line', 'city', 'state', 'postal_code', 'country']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class TrackOrderForm(forms.Form):
    order_number = forms.IntegerField(label='Order Number', widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter your order number'}))

def track_order(request):
    shop_user = request.shop_user if getattr(request, 'shop_user', None) else (request.user if request.user.is_authenticated else None)
    if not shop_user:
        return redirect('login')
    status = None
    order = None
    if request.method == 'POST':
        form = TrackOrderForm(request.POST)
        if form.is_valid():
            order_number = form.cleaned_data['order_number']
            try:
                order = Order.objects.get(id=order_number, user=request.shop_user) # Filter by user
                status = order.tracking_status
            except Order.DoesNotExist:
                status = 'Order not found or access denied.'
    else:
        form = TrackOrderForm()
    return render(request, 'store/track_order.html', {'form': form, 'status': status, 'order': order})

# View cart
def cart(request):
    shop_user = request.shop_user if getattr(request, 'shop_user', None) else (request.user if request.user.is_authenticated else None)
    if not shop_user:
        return redirect('login')
    cart_items = CartItem.objects.filter(user=shop_user)
    total = sum(item.product.price * item.quantity for item in cart_items)
    address_form = AddressForm()
    quantity_range = range(1, 11)
    if request.method == 'POST':
        address_form = AddressForm(request.POST)
        if address_form.is_valid():
            user_id = request.session.get('shop_user_id')
            from django.contrib.auth.models import User
            shop_user = User.objects.get(id=user_id)
            address = address_form.save(commit=False)
            address.user = shop_user
            address.save()

            # Create order and decrement size-level stock atomically
            with transaction.atomic():
                order = Order.objects.create(user=shop_user, address=address, total=total)

                # For each cart item, lock the corresponding SizeStock row and verify availability
                for cart_item in cart_items.select_for_update():
                    try:
                        size_row = SizeStock.objects.select_for_update().get(product=cart_item.product, size=cart_item.size)
                    except SizeStock.DoesNotExist:
                        transaction.set_rollback(True)
                        return HttpResponse('Product size not available.', status=400)

                    if size_row.stock < cart_item.quantity:
                        transaction.set_rollback(True)
                        return HttpResponse(f'Insufficient stock for {cart_item.product.name} size {cart_item.size}.', status=400)

                    # Deduct stock
                    size_row.stock -= cart_item.quantity
                    # ensure stock never goes below zero
                    if size_row.stock < 0:
                        size_row.stock = 0
                    size_row.mark_status()
                    size_row.save()

                    # Create order item snapshot including size
                    OrderItem.objects.create(order=order, product=cart_item.product, size=cart_item.size, quantity=cart_item.quantity, price=cart_item.product.price)

                # After all deductions, delete cart items
                cart_items.delete()

            return render(request, 'store/order_success.html', {'order': order, 'show_order_id_modal': True})
    return render(request, 'store/cart.html', {'cart_items': cart_items, 'total': total, 'address_form': address_form, 'quantity_range': quantity_range})

def remove_from_cart(request, item_id):
    shop_user = request.shop_user if getattr(request, 'shop_user', None) else (request.user if request.user.is_authenticated else None)
    if not shop_user:
        return redirect('login')
    CartItem.objects.filter(id=item_id, user=shop_user).delete()
    return redirect('cart')

def update_cart_item(request, item_id):
    shop_user = request.shop_user if getattr(request, 'shop_user', None) else (request.user if request.user.is_authenticated else None)
    if not shop_user:
        return redirect('login')
    cart_item = CartItem.objects.get(id=item_id, user=shop_user)
    if request.method == 'POST':
        selected = request.POST.get('quantity')
        menual = request.POST.get('menual_quantity')
        try:
            if menual:
                qty = int(menual)
            else:
                qty = int(selected)
                if qty == 11:  # 10+ chosen but no menual provided
                    return redirect('cart')
            if qty > 0:
                # Check size-level availability before updating
                try:
                    size_row = SizeStock.objects.get(product=cart_item.product, size=cart_item.size)
                except SizeStock.DoesNotExist:
                    return redirect('cart')
                if size_row.stock + cart_item.quantity < qty:  # allow reducing or same
                    # not enough stock to increase to desired qty
                    messages.error(request, f'Insufficient stock for size {cart_item.size}.')
                    return redirect('cart')
                cart_item.quantity = qty
                cart_item.save()
        except (ValueError, TypeError):
            pass
    return redirect('cart')

class StoreLoginView(LoginView):
    template_name = 'store/login.html'
    success_url = reverse_lazy('user_home')

    def form_valid(self, form):
        user = form.get_user()
        try:
            login(self.request, user)
        except Exception:
            pass
        self.request.session['shop_user_authenticated'] = True
        self.request.session['shop_user_id'] = user.id
        self.request.session['shop_user_username'] = user.username
        self.request.session['shop_user_email'] = user.email
        self.request.session['shop_user_date_joined'] = str(user.date_joined)
        guest_wishlist = self.request.session.pop('guest_wishlist', None)
        if guest_wishlist and isinstance(guest_wishlist, list):
            for pid in guest_wishlist:
                try:
                    prod_id = int(pid)
                except Exception:
                    continue
                try:
                    prod = Product.objects.get(pk=prod_id)
                except Product.DoesNotExist:
                    continue
                Wishlist.objects.get_or_create(user=user, product=prod)
        cart_intent = self.request.session.pop('cart_intent', None)
        if cart_intent:
            try:
                product_id = int(cart_intent.get('product_id'))
                quantity = int(cart_intent.get('quantity') or 1)
            except Exception:
                return redirect('cart')
            size = cart_intent.get('size')
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                return redirect('cart')
            if size not in dict(CartItem.SIZE_CHOICES):
                return redirect('cart')
            try:
                size_row = SizeStock.objects.get(product=product, size=size)
            except SizeStock.DoesNotExist:
                return redirect('cart')
            existing_qty = 0
            existing = CartItem.objects.filter(user=user, product=product, size=size).first()
            if existing:
                existing_qty = existing.quantity
            if size_row.stock < existing_qty + quantity:
                return redirect('cart')
            cart_item, created = CartItem.objects.get_or_create(user=user, product=product, size=size)
            if not created:
                cart_item.quantity += quantity
            else:
                cart_item.quantity = quantity
            cart_item.save()
            return redirect('user_home')
        return redirect(self.get_success_url())


@require_POST
def wishlist_add(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'login_required': True}, status=401)
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    pid = data.get('product_id') or request.POST.get('product_id')
    if not pid:
        return JsonResponse({'ok': False, 'error': 'product_id required'}, status=400)
    try:
        product = Product.objects.get(pk=int(pid))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid product'}, status=400)
    obj, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    return JsonResponse({'ok': True, 'created': created, 'message': 'Added to wishlist'})


@require_POST
def wishlist_remove(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'login_required': True}, status=401)
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    pid = data.get('product_id') or request.POST.get('product_id')
    if not pid:
        return JsonResponse({'ok': False, 'error': 'product_id required'}, status=400)
    Wishlist.objects.filter(user=request.user, product_id=pid).delete()
    return JsonResponse({'ok': True, 'message': 'Removed from wishlist'})


def wishlist_api(request):
    """Return JSON list of wishlisted product ids for authenticated user."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'login_required': True}, status=401)
    items = Wishlist.objects.filter(user=request.user).select_related('product')
    data = [{'id': w.product.id, 'name': w.product.name, 'price': str(w.product.price), 'image': w.product.image.url if w.product.image else ''} for w in items]
    return JsonResponse({'ok': True, 'items': data})


def wishlist_status(request):
    """Return whether the given product_id is in the authenticated user's wishlist.
    GET param: product_id
    """
    pid = request.GET.get('product_id')
    if not pid:
        return JsonResponse({'ok': False, 'error': 'product_id required'}, status=400)
    try:
        pid_int = int(pid)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid product_id'}, status=400)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': True, 'is_wishlisted': False, 'login_required': True})
    exists = Wishlist.objects.filter(user=request.user, product_id=pid_int).exists()
    return JsonResponse({'ok': True, 'is_wishlisted': exists})


@login_required
@require_POST
def wishlist_move_to_cart(request):
    """Move product from wishlist to cart for logged-in user."""
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    pid = data.get('product_id') or request.POST.get('product_id')
    if not pid:
        return JsonResponse({'ok': False, 'error': 'product_id required'}, status=400)
    try:
        product = Product.objects.get(pk=int(pid))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid product'}, status=400)
    # create or increment cart item with default size M if not provided
    size = data.get('size') or request.POST.get('size') or 'M'
    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product, size=size)
    if not created:
        cart_item.quantity += 1
    else:
        cart_item.quantity = 1
    cart_item.save()
    # remove from wishlist
    Wishlist.objects.filter(user=request.user, product=product).delete()
    return JsonResponse({'ok': True, 'message': 'Moved to cart'})


def wishlist_page(request):
    if not request.user.is_authenticated:
        return redirect('login')
    items = Wishlist.objects.filter(user=request.user).select_related('product').order_by('-created_at')
    return render(request, 'store/wishlist.html', {'items': items})


@require_POST
def wishlist_guest_save(request):
    """Save guest wishlist (from client localStorage) into server session so it
    can be merged on login.
    Expects JSON {items: [product_id, ...]} or form POST `items[]`.
    """
    try:
        data = json.loads(request.body.decode() or '{}')
    except Exception:
        data = request.POST
    items = data.get('items') or request.POST.getlist('items[]') or []
    # normalize to ints
    out = []
    for p in items:
        try:
            out.append(int(p))
        except Exception:
            continue
    request.session['guest_wishlist'] = out
    return JsonResponse({'ok': True, 'saved': len(out)})


@login_required
@require_POST
def save_for_later(request):
    """Move a CartItem (by id) into Wishlist for logged-in user and delete cart item.
    Does not affect inventory.
    """
    cart_item_id = request.POST.get('cart_item_id')
    if not cart_item_id:
        messages.error(request, 'Missing cart item id')
        return redirect('cart')
    try:
        ci = CartItem.objects.get(id=int(cart_item_id), user=request.user)
    except CartItem.DoesNotExist:
        messages.error(request, 'Cart item not found')
        return redirect('cart')
    Wishlist.objects.get_or_create(user=request.user, product=ci.product)
    ci.delete()
    messages.success(request, 'Saved for later')
    return redirect('wishlist_page')


from django.contrib.auth.models import User

def signup(request):
    error_message = None
    form_errors = None
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        username = request.POST.get('username')
        from .models import DeliveryPartnerUser
        if username and User.objects.filter(username=username).exists():
            error_message = 'Your account already exists. Please login.'
        elif username and DeliveryPartnerUser.objects.filter(username=username).exists():
            error_message = 'This username is reserved for a delivery partner. Please choose a different username.'
        elif form.is_valid():
            form.save()
            return redirect('login')
        else:
            form_errors = form.errors
    else:
        form = UserCreationForm()
    return render(request, 'store/signup.html', {'form': form, 'error_message': error_message, 'form_errors': form_errors})

# Authenticated user's home (same functionality as public home)
def user_home(request):
    categories = Category.objects.all()
    return render(request, 'store/user_home.html', {
        'categories': categories,
    })


def profile(request):
    if not request.shop_user:
        return redirect('login')
    user_id = request.shop_user.id
    username = request.shop_user.username
    email = request.shop_user.email
    date_joined = request.shop_user.date_joined
    addresses = Address.objects.filter(user=request.shop_user)
    recent_orders = Order.objects.filter(user=request.shop_user).order_by('-created_at')[:5]
    profile_user = {
        'username': username,
        'email': email,
        'date_joined': date_joined,
    }
    return render(request, 'store/profile.html', {
        'profile_user': profile_user,
        'addresses': addresses,
        'recent_orders': recent_orders,
    })


def about(request):
    return render(request, 'store/about.html')


def support(request):
    success = False
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        reason = request.POST.get('reason')
        request_call_back = request.POST.get('request_call_back') == 'on'
        if not (username and email and mobile):
            error = 'Please provide username, email, and mobile.'
        else:
            SupportRequest.objects.create(
                username=username,
                email=email,
                mobile=mobile,
                reason=reason or '',
                request_call_back=request_call_back
            )
            success = True
    return render(request, 'store/support.html', {'success': success, 'error': error})


def admin_logout_view(request):
    # menually remove Django's authentication keys from the session
    if '_auth_user_id' in request.session:
        del request.session['_auth_user_id']
    if '_auth_user_backend' in request.session:
        del request.session['_auth_user_backend']
    if '_auth_user_hash' in request.session:
        del request.session['_auth_user_hash']
    
    # Optionally, clear messages related to authentication
    from django.contrib import messages
    for message in messages.get_messages(request):
        # Keep only non-authentication related messages
        pass # No need to re-add them, just don't process them here

    return redirect('/admin/login/')
