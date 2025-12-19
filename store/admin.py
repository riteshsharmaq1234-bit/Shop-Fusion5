from django.contrib import admin, messages
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings
from .models import Category, Product, CartItem, Address, Order, SupportRequest, SizeStock
from django.db.models import F
from django.http import HttpResponseRedirect
from django.urls import reverse


def restock_sizes_action(modeladmin, request, queryset):
    count = 0
    for ss in queryset:
        default_qty = (ss.product.initial_total_stock // 5) if ss.product.initial_total_stock else 2
        if default_qty <= 0:
            default_qty = 2
        if ss.restock_to(default_qty):
            count += 1
    messages.success(request, f"Restocked {count} size(s).")
restock_sizes_action.short_description = 'Restock selected sizes to default quantity'


class SizeStockInline(admin.TabularInline):
    model = SizeStock
    extra = 0
    readonly_fields = ('status',)
    class SizeStockInlineForm(forms.ModelForm):
        class Meta:
            model = SizeStock
            fields = '__all__'

        def validate_unique(self):
            # Skip the default unique_together validation for product+size here
            # so that duplicates can be merged in the formset save logic.
            return

    class SizeStockInlineFormset(forms.BaseInlineFormSet):
        def save_new(self, form, commit=True):
            # When an inline attempts to create a SizeStock that already exists for
            # this product+size, merge by incrementing the existing stock instead
            # of creating a new row (prevents unique constraint errors).
            size = form.cleaned_data.get('size')
            stock = form.cleaned_data.get('stock') or 0
            product = self.instance
            ss, created = SizeStock.objects.get_or_create(
                product=product,
                size=size,
                defaults={'stock': stock, 'status': SizeStock.STATUS_IN if stock > 0 else SizeStock.STATUS_OUT},
            )
            if not created:
                # Increment existing stock atomically to avoid race conditions
                SizeStock.objects.filter(pk=ss.pk).update(stock=F('stock') + stock)
                ss.refresh_from_db()
                ss.mark_status()
                if commit:
                    ss.save(update_fields=['stock', 'status'])
            return ss

    form = SizeStockInlineForm
    formset = SizeStockInlineFormset


class ProductAdmin(admin.ModelAdmin):
    inlines = [SizeStockInline]

    actions = ['restock_product_sizes']

    def restock_product_sizes(self, request, queryset):
        """Restock all sizes for selected products to their per-size default."""
        count = 0
        for product in queryset:
            sizes = SizeStock.objects.filter(product=product)
            # compute per-size default
            per_size_default = (product.initial_total_stock // 5) if product.initial_total_stock else getattr(settings, 'RESTOCK_SIZE_QUANTITY', 2)
            if per_size_default <= 0:
                per_size_default = getattr(settings, 'RESTOCK_SIZE_QUANTITY', 2)
            for ss in sizes:
                if ss.restock_to(per_size_default):
                    count += 1
        messages.success(request, f"Restocked {count} size entries for selected products.")

    restock_product_sizes.short_description = 'Restock sizes for selected products to defaults'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Inline for CartItem in Order
class CartItemInline(admin.TabularInline):
    model = Order.items.through
    extra = 1


class OrderAdmin(admin.ModelAdmin):
    inlines = [CartItemInline]
    exclude = ('items',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            from django.contrib.auth.models import User
            kwargs["queryset"] = User.objects.exclude(is_superuser=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SizeStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'size', 'stock', 'status')
    list_filter = ('product__category', 'size', 'status')
    actions = [restock_sizes_action]
    class SizeStockAdminForm(forms.ModelForm):
        class Meta:
            model = SizeStock
            fields = '__all__'

        def validate_unique(self):
            # Skip unique_together validation for admin form so save_model
            # can merge duplicates (increment existing stock) instead of
            # raising a ValidationError.
            return

        def _post_clean(self):
            # Suppress unique_together ValidationError for product+size so the
            # admin save flow can merge duplicates instead of failing here.
            try:
                super()._post_clean()
            except ValidationError as e:
                msgs = e.messages if hasattr(e, 'messages') else []
                dup_related = any('already exists' in str(m).lower() for m in msgs)
                if dup_related:
                    # swallow duplicate-related validation errors
                    return
                raise

        def clean_stock(self):
            val = self.cleaned_data.get('stock')
            if val is None:
                return 0
            if val < 0:
                raise ValidationError('Stock cannot be negative.')
            return val

    form = SizeStockAdminForm
    def save_model(self, request, obj, form, change):
        """When adding a SizeStock via the admin add form, merge with existing
        product+size rows by incrementing stock instead of creating a duplicate.
        """
        if not change:
            existing = SizeStock.objects.filter(product=obj.product, size=obj.size).first()
            if existing:
                # increment atomically
                from django.db.models import F
                SizeStock.objects.filter(pk=existing.pk).update(stock=F('stock') + (obj.stock or 0))
                existing.refresh_from_db()
                existing.mark_status()
                existing.save(update_fields=['stock', 'status'])
                messages.success(request, f"Updated existing size stock for {obj.product} ({obj.size}).")
                return
        super().save_model(request, obj, form, change)

    def add_view(self, request, form_url='', extra_context=None):
        """Override add_view to gracefully handle duplicate product+size
        submissions produced by the admin add form. If a duplicate exists,
        increment the existing stock and redirect with a success message
        instead of showing the validation error.
        """
        if request.method == 'POST':
            Form = self.get_form(request)
            form = Form(request.POST, request.FILES)
            if form.is_valid():
                return super().add_view(request, form_url, extra_context)
            # If validation failed due to duplicate product+size, merge instead
            non_field = form.non_field_errors()
            dup_flag = any('already exists' in str(e).lower() for e in non_field)
            if dup_flag:
                product_id = request.POST.get('product')
                size = request.POST.get('size')
                try:
                    stock_val = int(request.POST.get('stock') or 0)
                except Exception:
                    stock_val = 0
                existing = SizeStock.objects.filter(product_id=product_id, size=size).first()
                if existing:
                    SizeStock.objects.filter(pk=existing.pk).update(stock=F('stock') + stock_val)
                    existing.refresh_from_db()
                    existing.mark_status()
                    existing.save(update_fields=['stock', 'status'])
                    messages.success(request, f"Updated existing size stock for {existing.product} ({existing.size}).")
                    return HttpResponseRedirect(reverse('admin:store_sizestock_changelist'))
        return super().add_view(request, form_url, extra_context)


admin.site.register(Category)
admin.site.register(Product, ProductAdmin)
admin.site.register(SizeStock, SizeStockAdmin)
admin.site.register(CartItem)
admin.site.register(Address)
admin.site.register(Order, OrderAdmin)
admin.site.register(SupportRequest)
