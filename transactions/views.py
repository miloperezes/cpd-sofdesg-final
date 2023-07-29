from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    View, 
    ListView,
    CreateView,
    UpdateView,
    DeleteView
)
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import (
    PurchaseBill, 
    Supplier, 
    PurchaseItem,
    PurchaseBillDetails,
    SaleBill,  
    SaleItem,
    SaleBillDetails
)
from .forms import (
    SelectSupplierForm, 
    PurchaseItemFormset,
    PurchaseDetailsForm, 
    SupplierForm, 
    SaleForm,
    SaleItemFormset,
    SaleDetailsForm
)
from inventory.models import Stock
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views import View
from .models import PurchaseBill
import csv
from django.http import HttpResponse

# shows a lists of all suppliers
class SupplierListView(ListView):
    model = Supplier
    template_name = "suppliers/suppliers_list.html"
    queryset = Supplier.objects.filter(is_deleted=False)
    paginate_by = 10

    def post(self, request, *args, **kwargs):
        supplier = self.get_object()
        supplier.comment = request.POST.get('comment', '')  # Get the value of the comment field from the form
        supplier.save()

# used to add a new supplier
class SupplierCreateView(SuccessMessageMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    success_url = '/transactions/suppliers'
    success_message = "Supplier has been created successfully"
    template_name = "suppliers/edit_supplier.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = 'New Supplier'
        context["savebtn"] = 'Add Supplier'
        return context     


# used to update a supplier's info
class SupplierUpdateView(SuccessMessageMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    success_url = '/transactions/suppliers'
    success_message = "Supplier details has been updated successfully"
    template_name = "suppliers/edit_supplier.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = 'Edit Supplier'
        context["savebtn"] = 'Save Changes'
        context["delbtn"] = 'Delete Supplier'
        return context


# used to delete a supplier
class SupplierDeleteView(View):
    template_name = "suppliers/delete_supplier.html"
    success_message = "Supplier has been deleted successfully"

    def get(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk)
        return render(request, self.template_name, {'object' : supplier})

    def post(self, request, pk):  
        supplier = get_object_or_404(Supplier, pk=pk)
        supplier.is_deleted = True
        supplier.save()                                               
        messages.success(request, self.success_message)
        return redirect('suppliers-list')


# used to view a supplier's profile
class SupplierView(View):
    def create_supplier(request):
        if request.method == 'POST':
            form = SupplierForm(request.POST)
            if form.is_valid():
                form.save()  # Save the form data, including the comment field
                return redirect('suppliers-list')
        else:
            form = SupplierForm()
        context = {'form': form}
        return render(request, 'suppliers/create_supplier.html', context)
    def get(self, request, name):
        supplierobj = get_object_or_404(Supplier, name=name)
        bill_list = PurchaseBill.objects.filter(supplier=supplierobj)
        page = request.GET.get('page', 1)
        paginator = Paginator(bill_list, 10)
        try:
            bills = paginator.page(page)
        except PageNotAnInteger:
            bills = paginator.page(1)
        except EmptyPage:
            bills = paginator.page(paginator.num_pages)
        context = {
            'supplier': supplierobj,
            'bills': bills,
            'saved_comment': supplierobj.comment  # Pass the 'comment' value to the template context
        }
        return render(request, 'suppliers/supplier.html', context)




# shows the list of bills of all purchases 
class PurchaseView(ListView):
    model = PurchaseBill
    template_name = "purchases/purchases_list.html"
    context_object_name = 'bills'
    ordering = ['-time']
    paginate_by = 10

    def get(self, request):
        purchases = PurchaseBill.objects.all()
        total_purchases = sum(purchase.get_total_price() for purchase in purchases)

        context = {
            'bills': purchases,
            'total_purchases': total_purchases,
        }
        return render(request, self.template_name, context)


# used to select the supplier
class SelectSupplierView(View):
    form_class = SelectSupplierForm
    template_name = 'purchases/select_supplier.html'

    def get(self, request, *args, **kwargs):                                    # loads the form page
        form = self.form_class
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):                                   # gets selected supplier and redirects to 'PurchaseCreateView' class
        form = self.form_class(request.POST)
        if form.is_valid():
            supplierid = request.POST.get("supplier")
            supplier = get_object_or_404(Supplier, id=supplierid)
            return redirect('new-purchase', supplier.pk)
        return render(request, self.template_name, {'form': form})


# used to generate a bill object and save items
class PurchaseCreateView(View):                                                 
    template_name = 'purchases/new_purchase.html'

    def get(self, request, pk):
        formset = PurchaseItemFormset(request.GET or None)                      # renders an empty formset
        supplierobj = get_object_or_404(Supplier, pk=pk)                        # gets the supplier object
        context = {
            'formset'   : formset,
            'supplier'  : supplierobj,
        }                                                                       # sends the supplier and formset as context
        return render(request, self.template_name, context)

    def post(self, request, pk):
        formset = PurchaseItemFormset(request.POST)                             # recieves a post method for the formset
        supplierobj = get_object_or_404(Supplier, pk=pk)                        # gets the supplier object
        if formset.is_valid():
            # saves bill
            billobj = PurchaseBill(supplier=supplierobj)                        # a new object of class 'PurchaseBill' is created with supplier field set to 'supplierobj'
            billobj.save()                                                      # saves object into the db
            # create bill details object
            billdetailsobj = PurchaseBillDetails(billno=billobj)
            billdetailsobj.save()
            for form in formset:                                                # for loop to save each individual form as its own object
                # false saves the item and links bill to the item
                billitem = form.save(commit=False)
                billitem.billno = billobj                                       # links the bill object to the items
                # gets the stock item
                stock = get_object_or_404(Stock, name=billitem.stock.name)       # gets the item
                # calculates the total price
                billitem.totalprice = billitem.perprice * billitem.quantity
                # updates quantity in stock db
                stock.quantity += billitem.quantity                              # updates quantity
                # saves bill item and stock
                stock.save()
                billitem.save()
            messages.success(request, "Purchased items have been registered successfully")
            return redirect('purchase-bill', billno=billobj.billno)
        formset = PurchaseItemFormset(request.GET or None)
        context = {
            'formset'   : formset,
            'supplier'  : supplierobj
        }
        return render(request, self.template_name, context)


# used to delete a bill object
class PurchaseDeleteView(SuccessMessageMixin, DeleteView):
    model = PurchaseBill
    template_name = "purchases/delete_purchase.html"
    success_url = '/transactions/purchases'
    
    def delete(self, *args, **kwargs):
        self.object = self.get_object()
        items = PurchaseItem.objects.filter(billno=self.object.billno)
        for item in items:
            stock = get_object_or_404(Stock, name=item.stock.name)
            if stock.is_deleted == False:
                stock.quantity -= item.quantity
                stock.save()
        messages.success(self.request, "Purchase bill has been deleted successfully")
        return super(PurchaseDeleteView, self).delete(*args, **kwargs)




# shows the list of bills of all sales 
class SaleView(ListView):
    model = SaleBill
    template_name = "sales/sales_list.html"
    context_object_name = 'bills'
    ordering = ['-time']
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_sold_price = SaleItem.objects.aggregate(total=Sum('totalprice'))['total']
        context['total_sold_price'] = total_sold_price
        return context


def export_sales_to_csv(request):
    # Retrieve the sales data from the database (similar to the 'SaleView' view)
    sales = SaleBill.objects.all()

    # Create the HttpResponse object with the appropriate CSV headers
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_list.csv"'

    # Create the CSV writer
    writer = csv.writer(response)

    # Write the CSV header
    writer.writerow(['Bill No.', 'Customer', 'Stocks Sold', 'Quantity Sold', 'Total Sold Price', 'Date'])

    # Write the data rows
    for sale in sales:
        stocks_sold = ", ".join([item.stock.name for item in sale.items.all()])
        quantities_sold = ", ".join([str(item.quantity) for item in sale.items.all()])
        total_price = sale.items.aggregate(total=Sum('totalprice'))['total']

        # Format the date as a string before writing it to the CSV file
        sale_date = sale.time.strftime('%Y-%m-%d')

        writer.writerow([sale.billno, sale.name, stocks_sold, quantities_sold, total_price, sale_date])

    return response

def export_purchases_to_csv(request):
    # Fetch all the purchases from the database
    purchases = PurchaseBill.objects.all()

    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="purchases.csv"'

    # Create a CSV writer using HttpResponse as the output file
    writer = csv.writer(response)

    # Write CSV header
    writer.writerow(['Bill No.', 'Supplier', 'Stocks Purchased', 'Quantity Purchased', 'Total Purchased Price', 'Purchased Date'])

    # Write CSV data rows
    for purchase in purchases:
        stocks_purchased = "\n".join([item.stock.name for item in purchase.get_items_list()])
        quantities_purchased = "\n".join([str(item.quantity) for item in purchase.get_items_list()])
        total_price = f"{purchase.get_total_price()}"
        purchased_date = purchase.time.strftime('%Y-%m-%d')  # Format the date as a string using strftime
        writer.writerow([purchase.billno, purchase.supplier.name, stocks_purchased, quantities_purchased, total_price, purchased_date])

    return response

# used to generate a bill object and save items
class SaleCreateView(View):
    template_name = 'sales/new_sale.html'

    def get(self, request):
        form = SaleForm(request.GET or None)
        formset = SaleItemFormset(request.GET or None)
        stocks = Stock.objects.filter(is_deleted=False)
        context = {
            'form': form,
            'formset': formset,
            'stocks': stocks,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = SaleForm(request.POST)
        formset = SaleItemFormset(request.POST)
        if form.is_valid() and formset.is_valid():
            sale_bill = form.save()
            for sale_item_form in formset:
                sale_item = sale_item_form.save(commit=False)
                stock = sale_item.stock

                if stock.is_deleted or stock.quantity < sale_item.quantity:
                    messages.error(request, f"Insufficient stock for {stock.name}.")
                    return redirect('new-sale')

                sale_item.billno = sale_bill
                sale_item.totalprice = sale_item.perprice * sale_item.quantity
                stock.quantity -= sale_item.quantity
                sale_item.save()
                stock.save()

            sale_bill_details = SaleBillDetails(billno=sale_bill)
            sale_bill_details.save()

            messages.success(request, "Sold items have been registered successfully")
            return redirect('sale-bill', billno=sale_bill.billno)
        else:
            # Debugging statements
            print(form.errors)
            for form in formset:
                print(form.errors)

        # If the form or formset is not valid, re-render the page with errors
        form = SaleForm(request.GET or None)
        formset = SaleItemFormset(request.GET or None)
        stocks = Stock.objects.filter(is_deleted=False)
        context = {
            'form': form,
            'formset': formset,
            'stocks': stocks,
        }
        return render(request, self.template_name, context)


# used to delete a bill object
class SaleDeleteView(SuccessMessageMixin, DeleteView):
    model = SaleBill
    template_name = "sales/delete_sale.html"
    success_url = '/transactions/sales'
    
    def delete(self, *args, **kwargs):
        self.object = self.get_object()
        items = SaleItem.objects.filter(billno=self.object.billno)
        for item in items:
            stock = get_object_or_404(Stock, name=item.stock.name)
            if stock.is_deleted == False:
                stock.quantity += item.quantity
                stock.save()
        messages.success(self.request, "Sale bill has been deleted successfully")
        return super(SaleDeleteView, self).delete(*args, **kwargs)


# used to display the purchase bill object
from django.shortcuts import get_object_or_404
from django.db.models import Sum

class PurchaseBillView(View):
    model = PurchaseBill
    template_name = "bill/purchase_bill.html"
    bill_base = "bill/bill_base.html"

    def get(self, request, billno):
        bill = get_object_or_404(PurchaseBill, billno=billno)
        items = PurchaseItem.objects.filter(billno=billno)
        total_amount = items.aggregate(total=Sum('totalprice'))['total']

        context = {
            'bill': bill,
            'items': items,
            'billdetails': get_object_or_404(PurchaseBillDetails, billno=billno),
            'bill_base': self.bill_base,
            'total_amount': total_amount,
        }
        return render(request, self.template_name, context)

    def post(self, request, billno):
        form = PurchaseDetailsForm(request.POST)
        if form.is_valid():
            billdetailsobj = PurchaseBillDetails.objects.get(billno=billno)
            
            billdetailsobj.eway = request.POST.get("eway")    
            billdetailsobj.veh = request.POST.get("veh")
            billdetailsobj.destination = request.POST.get("destination")
            billdetailsobj.po = request.POST.get("po")
            billdetailsobj.cgst = request.POST.get("cgst")
            billdetailsobj.sgst = request.POST.get("sgst")
            billdetailsobj.igst = request.POST.get("igst")
            billdetailsobj.cess = request.POST.get("cess")
            billdetailsobj.tcs = request.POST.get("tcs")
            billdetailsobj.total = request.POST.get("total")

            billdetailsobj.save()
            messages.success(request, "Bill details have been modified successfully")
        bill = get_object_or_404(PurchaseBill, billno=billno)
        items = PurchaseItem.objects.filter(billno=billno)
        total_amount = items.aggregate(total=Sum('totalprice'))['total']

        context = {
            'bill': bill,
            'items': items,
            'billdetails': get_object_or_404(PurchaseBillDetails, billno=billno),
            'bill_base': self.bill_base,
            'total_amount': total_amount,
        }
        return render(request, self.template_name, context)
    



# used to display the sale bill object
from django.shortcuts import get_object_or_404

class SaleBillView(View):
    model = SaleBill
    template_name = "bill/sale_bill.html"
    bill_base = "bill/bill_base.html"
    
    def get(self, request, billno):
        bill = SaleBill.objects.get(billno=billno)
        items = SaleItem.objects.filter(billno=billno)
        total_price = sum(item.totalprice for item in items)

        context = {
            'bill': bill,
            'items': items,
            'billdetails': get_object_or_404(SaleBillDetails, billno=billno),
            'bill_base': self.bill_base,
            'total_price': total_price,
        }
        return render(request, self.template_name, context)

    def post(self, request, billno):
        form = SaleDetailsForm(request.POST)
        if form.is_valid():
            items = SaleItem.objects.filter(billno=billno)
            total_price = sum(item.totalprice for item in items)
            
            billdetailsobj = get_object_or_404(SaleBillDetails, billno=billno)
            billdetailsobj.eway = request.POST.get("eway")    
            billdetailsobj.veh = request.POST.get("veh")
            billdetailsobj.destination = request.POST.get("destination")
            billdetailsobj.po = request.POST.get("po")
            billdetailsobj.cgst = request.POST.get("cgst")
            billdetailsobj.sgst = request.POST.get("sgst")
            billdetailsobj.igst = request.POST.get("igst")
            billdetailsobj.cess = request.POST.get("cess")
            billdetailsobj.tcs = request.POST.get("tcs")
            billdetailsobj.total = total_price  # Update the total price
            billdetailsobj.save()
            messages.success(request, "Bill details have been modified successfully")

        context = {
            'bill': SaleBill.objects.get(billno=billno),
            'items': SaleItem.objects.filter(billno=billno),
            'billdetails': get_object_or_404(SaleBillDetails, billno=billno),
            'bill_base': self.bill_base,
        }
        return render(request, self.template_name, context)