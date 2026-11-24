"""设备台账（mod16）请求与响应契约：守卫分布、调拨、报废、租赁与盘点的字段校验。"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Name = Annotated[str, Field(min_length=1)]
Month = Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
Number = Annotated[Decimal, Field(max_digits=18, decimal_places=4)]
Positive = Annotated[Number, Field(gt=0)]
Price = Annotated[Number, Field(ge=0)]
ItemCategory = Literal["equipment", "turnover"]
Category = Literal["tool", "turnover"]
Status = Literal["in_use", "damaged", "pending_scrap"]
Scope = Literal["current_asset", "fixed_asset", "off_book"]
RentalFlag = Literal["yes", "no", "pending"]
Billing = Literal["normal", "skip_month", "stopped", "blank"]
Ids = Annotated[list[Annotated[int, Field(gt=0)]], Field(min_length=1)]
ProjectId = Annotated[int, Field(gt=0)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Preview(Input):
    name: Name
    purchase_date: date
    quantity: Positive = Decimal(1)
    item_category: ItemCategory = "equipment"

    @model_validator(mode="after")
    def whole_equipment(self):
        if self.item_category == "equipment" and self.quantity != int(self.quantity):
            raise ValueError("逐台编号的设备数量须为正整数")
        if self.item_category == "equipment" and self.quantity > 10000:
            raise ValueError("逐台编号每批最多一万台，请分批登记")
        return self


class EquipmentCreate(Preview):
    expected_codes: list[str] | None = None
    spec: str | None = None
    unit: str | None = None
    purchase_project: Name | None = None
    purchase_project_id: ProjectId | None = None
    purchase_project_custom: str | None = None
    current_project: Name | None = Field(None, deprecated=True, description="兼容旧客户端，初始位置以购买项目为准")
    current_project_id: ProjectId | None = Field(None, deprecated=True, description="兼容旧客户端，初始位置以购买项目为准")
    current_project_custom: str | None = Field(None, deprecated=True, description="兼容旧客户端，初始位置以购买项目为准")
    purchase_price: Price | None = None
    custom_unit_price: Price | None = None
    asset_scope: Scope = "current_asset"
    in_rental: RentalFlag = "yes"
    status: Status = "in_use"
    remark: str | None = None
    target_month: Month | None = None


class EquipmentPatch(Input):
    name: Name = Field(default_factory=lambda: "")
    spec: str | None = None
    unit: str | None = None
    purchase_date: date | None = None
    purchase_project: Name | None = None
    purchase_project_id: ProjectId | None = None
    purchase_project_custom: str | None = None
    purchase_price: Price | None = None
    status: Status = "in_use"
    asset_scope: Scope = "current_asset"
    in_rental: RentalFlag = "yes"
    remark: str | None = None


class Transfer(Input):
    expected_from_projects: dict[int, str] | None = None
    equipment_ids: Ids
    to_project: Name | None = None
    to_project_id: ProjectId | None = None
    to_project_custom: str | None = None
    transfer_date: date
    remark: str | None = None


class TransferDeleteResult(BaseModel):
    deleted_transfer_id: int
    equipment_id: int
    reverted_project: str
    reverted_project_id: int | None
    reverted_project_custom: str | None


class Scrap(Input):
    equipment_ids: Ids | None = None
    equipment_id: Annotated[int, Field(gt=0)] | None = None
    scrap_date: date
    reason: str | None = None

    @model_validator(mode="after")
    def single_or_batch(self):
        if (self.equipment_id is None) == (self.equipment_ids is None):
            raise ValueError("请选择一个设备或一组设备")
        return self


class Retry(Input):
    equipment_ids: list[int] = Field(default_factory=list)
    transfer_ids: list[int] = Field(default_factory=list)


class InventoryCreate(Input):
    category: Category
    name: Name
    spec: str | None = None
    unit: str | None = None
    unit_price: Price | None = None
    book_qty: Number
    count_qty: Number
    diff_qty: Number | None = None
    diff_reason: str | None = None
    sort_order: int = 0


class InventoryPatch(Input):
    name: Name = Field(default_factory=lambda: "")
    spec: str | None = None
    unit: str | None = None
    unit_price: Price | None = None
    book_qty: Number = Decimal(0)
    count_qty: Number = Decimal(0)
    diff_qty: Number | None = None
    diff_reason: str | None = None
    sort_order: int = 0


class RentPatch(Input):
    quantity: Positive = Decimal(1)
    custom_unit_price: Price | None = None
    distribution_note: str | None = None
    billing_status: Billing = "normal"


class Resolve(Input):
    choice: Literal["this_month", "next_month", "from_project", "to_project",
                    "stop_this_month", "charge_this_month"]


class MonthInput(Input):
    month: Month


class Reorder(MonthInput):
    project_name: Name
    project_id: ProjectId | None = None
    ordered_line_ids: Ids
