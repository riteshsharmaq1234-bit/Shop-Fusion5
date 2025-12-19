
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# Completely separate table for delivery partner users
class DeliveryPartnerUser(models.Model):
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    id_proof = models.CharField(max_length=100, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

class Category(models.Model):
    CATEGORY_CHOICES = [
        ('men', 'Men'),
        ('Woman', 'Woman'),
    ]
    name = models.CharField(max_length=100, choices=CATEGORY_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()

class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='products/')
    specification = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # initial total stock to distribute across sizes when product is created
    initial_total_stock = models.PositiveIntegerField(default=10)
    # Note: per-size default is derived from `initial_total_stock` (even distribution)

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        # Sum of size-level stocks if any exist, otherwise fall back to initial_total_stock
        sizes = self.sizestock_set.all()
        if sizes.exists():
            return sum(s.stock for s in sizes)
        return self.initial_total_stock

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # size selection for this cart line
    SIZE_CHOICES = [
        ('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL'), ('XXL', 'XXL')
    ]
    size = models.CharField(max_length=4, choices=SIZE_CHOICES, default='M')
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"

    @property
    def subtotal(self):
        return self.product.price * self.quantity

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address_line = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.address_line}, {self.city}, {self.state}, {self.country}"

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.ForeignKey(Address, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    items = models.ManyToManyField(CartItem)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    tracking_status = models.CharField(max_length=100, default='Order Placed')

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey('Order', related_name='order_items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.CharField(max_length=4, choices=CartItem.SIZE_CHOICES, default='M')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"


class SizeStock(models.Model):
    SIZE_CHOICES = [
        ('S', 'S'), ('M', 'M'), ('L', 'L'), ('XL', 'XL'), ('XXL', 'XXL')
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    size = models.CharField(max_length=4, choices=SIZE_CHOICES)
    stock = models.PositiveIntegerField(default=0)
    STATUS_IN = 'IN_STOCK'
    STATUS_OUT = 'OUT_OF_STOCK'
    STATUS_CHOICES = [
        (STATUS_IN, 'In Stock'),
        (STATUS_OUT, 'Out of Stock'),
    ]
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_IN)

    class Meta:
        unique_together = ('product', 'size')

    def __str__(self):
        return f"{self.product.name} [{self.size}] = {self.stock}"

    def mark_status(self):
        """Set status based on current stock value."""
        self.status = self.STATUS_IN if self.stock > 0 else self.STATUS_OUT
        return self.status

    def restock_to(self, qty):
        """Restock this size to a target qty (idempotent)."""
        if qty is None:
            return False
        if self.stock != qty:
            self.stock = qty
            self.mark_status()
            self.save(update_fields=['stock', 'status'])
            return True
        return False


@receiver(post_save, sender=Product)
def create_size_stocks(sender, instance, created, **kwargs):
    """Ensure each product has size-level stock rows distributed evenly from initial_total_stock.

    This runs after save and will create missing SizeStock rows. If no SizeStock rows exist,
    it's treated as a fresh product and initial_total_stock is distributed evenly.
    """
    sizes = ['S', 'M', 'L', 'XL', 'XXL']
    existing = {s.size for s in instance.sizestock_set.all()}
    # If none exist, distribute initial_total_stock across sizes
    if not existing:
        total = instance.initial_total_stock or 10
        base = total // len(sizes)
        rem = total % len(sizes)
        for i, sz in enumerate(sizes):
            qty = base + (1 if i < rem else 0)
            # create if missing, otherwise leave existing stock alone
            SizeStock.objects.get_or_create(product=instance, size=sz, defaults={'stock': qty, 'status': SizeStock.STATUS_IN if qty > 0 else SizeStock.STATUS_OUT})
    else:
        # Create any missing sizes with zero stock
        for sz in sizes:
            if sz not in existing:
                SizeStock.objects.get_or_create(product=instance, size=sz, defaults={'stock': 0, 'status': SizeStock.STATUS_OUT})


from django.db.models.signals import pre_save, post_save


@receiver(pre_save, sender=Order)
def order_pre_save(sender, instance, **kwargs):
    """Capture previous tracking_status before Order is saved so post_save can
    detect a transition (e.g., to 'Delivered').
    """
    if instance.pk:
        try:
            prev = Order.objects.get(pk=instance.pk)
            instance._previous_tracking_status = prev.tracking_status
        except Order.DoesNotExist:
            instance._previous_tracking_status = None
    else:
        instance._previous_tracking_status = None


@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """When an order's tracking_status transitions to a delivered/completed state,
    restock any size-level SKU that is currently out of stock back to the product's
    `default_size_stock` quantity.
    """
    prev = getattr(instance, '_previous_tracking_status', None)
    new = (instance.tracking_status or '').lower()
    if prev != instance.tracking_status and ('delivered' in new or 'completed' in new):
        # Restock sizes that are currently zero for items in this order
        for oi in instance.order_items.select_related('product'):
            try:
                ss = SizeStock.objects.get(product=oi.product, size=oi.size)
            except SizeStock.DoesNotExist:
                ss = None
            # Determine restock target per-size by evenly dividing product.initial_total_stock
            default_qty = (oi.product.initial_total_stock // 5) if oi.product.initial_total_stock else 2
            if default_qty <= 0:
                default_qty = 2
            if ss is None:
                # create or get existing (handle race conditions) and ensure status set
                status = SizeStock.STATUS_IN if default_qty > 0 else SizeStock.STATUS_OUT
                ss, created = SizeStock.objects.get_or_create(product=oi.product, size=oi.size, defaults={'stock': default_qty, 'status': status})
                if not created and ss.stock == 0:
                    ss.restock_to(default_qty)
            else:
                if ss.stock == 0:
                    # use restock helper which sets status and saves idempotently
                    ss.restock_to(default_qty)


class SupportRequest(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    mobile = models.CharField(max_length=30)
    reason = models.CharField(max_length=255, blank=True)
    request_call_back = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SupportRequest {self.id} - {self.username}"


class Wishlist(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"Wishlist: {self.user.username} - {self.product.name}"
