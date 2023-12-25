from datetime import datetime
from enum import Enum
from typing import List,Optional


class Method():
    Get = '1'
    Post = '2'
    Put = '3'


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

class Urls:
    is_authorized = Struct(**{"url": "/api/IsAuthorized","method": Method.Get})
    administrative_divisions = Struct(**{"url": "/api/AdministrativeDivisions","method": Method.Get})
    customer_groupings = Struct(**{"url": "/api/CustomerGroupings","method": Method.Get})
    get_customers = Struct(**{"url": "/api/Customers","method": Method.Get})
    get_customer = Struct(**{"url": "/api/Customers/{0}","method": Method.Get})#/id
    post_customers = Struct(**{"url": "/api/Customers","method": Method.Post})
    put_customers = Struct(**{"url": "/api/Customers/{0}","method": Method.Put})#/id
    units = Struct(**{"url": "/api/Units","method": Method.Get})
    properties = Struct(**{"url": "/api/properties","method": Method.Get})
    stocks = Struct(**{"url": "/api/Stocks","method": Method.Get})
    items = Struct(**{"url": "/api/Items","method": Method.Get})
    item_image = Struct(**{"url": "/api/Items/{0}/Image/","method": Method.Get})
    inventories = Struct(**{"url": "/api/Items/Inventories/","method": Method.Get})
    sale_types = Struct(**{"url": "/api/Items/SaleTypes","method": Method.Get})
    price_note_items = Struct(**{"url": "/api/Items/PriceNoteItems","method": Method.Get})
    currencies = Struct(**{"url": "/api/Items/Currencies","method": Method.Get})
    get_quotations = Struct(**{"url": "/api/Items/Quotations","method": Method.Get})
    get_quotation = Struct(**{"url": "/api/Items/Quotations/{0}","method": Method.Get})#/id
    pos_quotations = Struct(**{"url": "/api/Items/Quotations/","method": Method.Post})


class CustomerAddress:
    GUID: str = None
    Title: str = None
    IsMain: bool = False
    CityRef: int = None
    Address: str = None
    ZipCode: str = None
    Latitude: float = None
    Longitude: float = None


class CustomerTypeCls(Enum):
    T1 = "حقیقی"
    T2 = "حقوقی"


class Customer:
    GUID: str = None
    PhoneNumber: Optional[str] = None
    CustomerType: int = CustomerTypeCls.T1
    Name: str = None
    LastName: str = None
    BirthDate: Optional[str] = None
    NationalID: Optional[str] = None
    EconomicCode: Optional[str] = None
    Addresses: Optional[List[CustomerAddress]] = None
    Version: int = None


class Quotation:
    GUID: str = None
    CurrencyRef: int = None
    Rate: float = None
    Date: Optional[datetime] = None
    ExpirationDate: datetime = None
    CustomerRef: int = None
    AddressRef: Optional[int] = None
    GUID: str = None
    GUID: str = None


if __name__ == '__main__':
    print(Struct(**{"url": "/api/Items/[0]/Image/","method": Method.Get}).__dict__)