class DeliveryPartnerRouter:
    """
    Routes DeliveryPartner model to the delivery_db database.
    """
    route_app_labels = {'store'}

    def db_for_read(self, model, **hints):
        if model.__name__ == 'DeliveryPartner':
            return 'delivery_db'
        return None

    def db_for_write(self, model, **hints):
        if model.__name__ == 'DeliveryPartner':
            return 'delivery_db'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1.__class__.__name__ == 'DeliveryPartner' or obj2.__class__.__name__ == 'DeliveryPartner':
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name == 'deliverypartner':
            return db == 'delivery_db'
        return db == 'default'
