package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.*
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

// ==================== Customer Use Cases ====================

class GetAllCustomersUseCase @Inject constructor(
    private val repository: ChannelCustomerRepository
) {
    operator fun invoke(): Flow<List<ChannelCustomer>> = repository.getAll()
}

class GetCustomerByIdUseCase @Inject constructor(
    private val repository: ChannelCustomerRepository
) {
    suspend operator fun invoke(id: Long): ChannelCustomer? = repository.getById(id)
}

class SaveCustomerUseCase @Inject constructor(
    private val repository: ChannelCustomerRepository
) {
    suspend operator fun invoke(customer: ChannelCustomer): Long {
        return if (customer.id == 0L) {
            repository.insert(customer)
        } else {
            repository.update(customer)
            customer.id
        }
    }
}

class DeleteCustomerUseCase @Inject constructor(
    private val repository: ChannelCustomerRepository
) {
    suspend operator fun invoke(customer: ChannelCustomer) = repository.delete(customer)
}

// ==================== Point Use Cases ====================

class GetAllPointsUseCase @Inject constructor(
    private val repository: PointRepository
) {
    operator fun invoke(): Flow<List<Point>> = repository.getAll()
}

class GetPointsByCustomerUseCase @Inject constructor(
    private val repository: PointRepository
) {
    operator fun invoke(customerId: Long): Flow<List<Point>> = repository.getByCustomerId(customerId)
}

class SavePointUseCase @Inject constructor(
    private val repository: PointRepository
) {
    suspend operator fun invoke(point: Point): Long {
        return if (point.id == 0L) {
            repository.insert(point)
        } else {
            repository.update(point)
            point.id
        }
    }
}

class DeletePointUseCase @Inject constructor(
    private val repository: PointRepository
) {
    suspend operator fun invoke(point: Point) = repository.delete(point)
}

// ==================== Supplier Use Cases ====================

class GetAllSuppliersUseCase @Inject constructor(
    private val repository: SupplierRepository
) {
    operator fun invoke(): Flow<List<Supplier>> = repository.getAll()
}

class GetSupplierByIdUseCase @Inject constructor(
    private val repository: SupplierRepository
) {
    suspend operator fun invoke(id: Long): Supplier? = repository.getById(id)
}

class GetSuppliersByCategoryUseCase @Inject constructor(
    private val repository: SupplierRepository
) {
    operator fun invoke(category: SupplierCategory): Flow<List<Supplier>> = repository.getByCategory(category)
}

class SaveSupplierUseCase @Inject constructor(
    private val repository: SupplierRepository
) {
    suspend operator fun invoke(supplier: Supplier): Long {
        return if (supplier.id == 0L) {
            repository.insert(supplier)
        } else {
            repository.update(supplier)
            supplier.id
        }
    }
}

class DeleteSupplierUseCase @Inject constructor(
    private val repository: SupplierRepository
) {
    suspend operator fun invoke(supplier: Supplier) = repository.delete(supplier)
}

// ==================== SKU Use Cases ====================

class GetAllSkusUseCase @Inject constructor(
    private val repository: SkuRepository
) {
    operator fun invoke(): Flow<List<Sku>> = repository.getAll()
}

class GetSkuByIdUseCase @Inject constructor(
    private val repository: SkuRepository
) {
    suspend operator fun invoke(id: Long): Sku? = repository.getById(id)
}

class GetSkusBySupplierUseCase @Inject constructor(
    private val repository: SkuRepository
) {
    operator fun invoke(supplierId: Long): Flow<List<Sku>> = repository.getBySupplierId(supplierId)
}

class GetSkusByTypeUseCase @Inject constructor(
    private val repository: SkuRepository
) {
    operator fun invoke(type: SkuType): Flow<List<Sku>> = repository.getByTypeLevel1(type)
}

class SaveSkuUseCase @Inject constructor(
    private val repository: SkuRepository
) {
    suspend operator fun invoke(sku: Sku): Long {
        return if (sku.id == 0L) {
            repository.insert(sku)
        } else {
            repository.update(sku)
            sku.id
        }
    }
}

class DeleteSkuUseCase @Inject constructor(
    private val repository: SkuRepository
) {
    suspend operator fun invoke(sku: Sku) = repository.delete(sku)
}

// ==================== External Partner Use Cases ====================

class GetAllPartnersUseCase @Inject constructor(
    private val repository: ExternalPartnerRepository
) {
    operator fun invoke(): Flow<List<ExternalPartner>> = repository.getAll()
}

class SavePartnerUseCase @Inject constructor(
    private val repository: ExternalPartnerRepository
) {
    suspend operator fun invoke(partner: ExternalPartner): Long {
        return if (partner.id == 0L) {
            repository.insert(partner)
        } else {
            repository.update(partner)
            partner.id
        }
    }
}

class DeletePartnerUseCase @Inject constructor(
    private val repository: ExternalPartnerRepository
) {
    suspend operator fun invoke(partner: ExternalPartner) = repository.delete(partner)
}

// ==================== Bank Account Use Cases ====================

class GetAllBankAccountsUseCase @Inject constructor(
    private val repository: BankAccountRepository
) {
    operator fun invoke(): Flow<List<BankAccount>> = repository.getAll()
}

class GetBankAccountsByOwnerTypeUseCase @Inject constructor(
    private val repository: BankAccountRepository
) {
    operator fun invoke(ownerType: OwnerType): Flow<List<BankAccount>> = repository.getByOwnerType(ownerType)
}

class GetDefaultBankAccountUseCase @Inject constructor(
    private val repository: BankAccountRepository
) {
    suspend operator fun invoke(ownerType: OwnerType): BankAccount? = repository.getDefaultByOwnerType(ownerType)
}

class SaveBankAccountUseCase @Inject constructor(
    private val repository: BankAccountRepository
) {
    suspend operator fun invoke(account: BankAccount): Long {
        return if (account.id == 0L) {
            repository.insert(account)
        } else {
            repository.update(account)
            account.id
        }
    }
}

class DeleteBankAccountUseCase @Inject constructor(
    private val repository: BankAccountRepository
) {
    suspend operator fun invoke(account: BankAccount) = repository.delete(account)
}
