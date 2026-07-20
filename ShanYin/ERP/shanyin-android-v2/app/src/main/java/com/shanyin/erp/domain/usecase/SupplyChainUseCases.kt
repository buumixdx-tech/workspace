package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.SupplyChainItemRepository
import com.shanyin.erp.domain.repository.SupplyChainRepository
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

// ==================== SupplyChain Use Cases ====================

class GetAllSupplyChainsUseCase @Inject constructor(
    private val repository: SupplyChainRepository
) {
    operator fun invoke(): Flow<List<SupplyChain>> = repository.getAll()
}

class GetSupplyChainByIdUseCase @Inject constructor(
    private val repository: SupplyChainRepository
) {
    suspend operator fun invoke(id: Long): SupplyChain? = repository.getById(id)
}

class GetSupplyChainsBySupplierUseCase @Inject constructor(
    private val repository: SupplyChainRepository
) {
    operator fun invoke(supplierId: Long): Flow<List<SupplyChain>> = repository.getBySupplierId(supplierId)
}

class GetSupplyChainsByTypeUseCase @Inject constructor(
    private val repository: SupplyChainRepository
) {
    operator fun invoke(type: SupplyChainType): Flow<List<SupplyChain>> = repository.getByType(type)
}

class SaveSupplyChainUseCase @Inject constructor(
    private val repository: SupplyChainRepository
) {
    suspend operator fun invoke(supplyChain: SupplyChain): Long {
        return if (supplyChain.id == 0L) {
            repository.insert(supplyChain)
        } else {
            repository.update(supplyChain)
            supplyChain.id
        }
    }
}

class DeleteSupplyChainUseCase @Inject constructor(
    private val repository: SupplyChainRepository,
    private val itemRepository: SupplyChainItemRepository
) {
    suspend operator fun invoke(supplyChain: SupplyChain) {
        // Delete all items first
        itemRepository.deleteBySupplyChainId(supplyChain.id)
        // Then delete the supply chain
        repository.delete(supplyChain)
    }
}

// ==================== SupplyChainItem Use Cases ====================

class GetSupplyChainItemsUseCase @Inject constructor(
    private val repository: SupplyChainItemRepository
) {
    operator fun invoke(supplyChainId: Long): Flow<List<SupplyChainItem>> =
        repository.getBySupplyChainId(supplyChainId)
}

class GetSkuPriceUseCase @Inject constructor(
    private val repository: SupplyChainItemRepository
) {
    suspend operator fun invoke(skuId: Long): SupplyChainItem? =
        repository.getBySkuId(skuId)
}

class SaveSupplyChainItemUseCase @Inject constructor(
    private val repository: SupplyChainItemRepository
) {
    suspend operator fun invoke(item: SupplyChainItem): Long {
        return if (item.id == 0L) {
            repository.insert(item)
        } else {
            repository.update(item)
            item.id
        }
    }
}

class SaveSupplyChainItemsUseCase @Inject constructor(
    private val repository: SupplyChainItemRepository
) {
    suspend operator fun invoke(items: List<SupplyChainItem>): List<Long> {
        return repository.insertAll(items)
    }
}

class DeleteSupplyChainItemUseCase @Inject constructor(
    private val repository: SupplyChainItemRepository
) {
    suspend operator fun invoke(item: SupplyChainItem) = repository.delete(item)
}

/**
 * 创建供应链协议（含SKU定价）
 */
class CreateSupplyChainUseCase @Inject constructor(
    private val saveSupplyChain: SaveSupplyChainUseCase,
    private val saveItems: SaveSupplyChainItemsUseCase,
    private val generateRules: GenerateRulesFromPaymentTermsUseCase
) {
    suspend operator fun invoke(
        supplierId: Long,
        supplierName: String,
        type: SupplyChainType,
        items: List<SupplyChainItem>,
        pricingConfig: PricingConfig? = null,
        paymentTerms: PaymentTerms? = null
    ): Long {
        val supplyChain = SupplyChain(
            supplierId = supplierId,
            supplierName = supplierName,
            type = type,
            pricingConfig = pricingConfig,
            paymentTerms = paymentTerms
        )
        val supplyChainId = saveSupplyChain(supplyChain)

        // Save items with the supply chain ID
        val itemsWithId = items.map { it.copy(supplyChainId = supplyChainId) }
        saveItems(itemsWithId)

        // 生成付款条款时间规则
        paymentTerms?.let { pt ->
            if (pt.prepaymentPercent > 0 || pt.paymentDays > 0) {
                generateRules(
                    relatedId = supplyChainId,
                    relatedType = RelatedType.SUPPLY_CHAIN,
                    prepaymentPercent = pt.prepaymentPercent,
                    balanceDays = pt.paymentDays
                )
            }
        }

        return supplyChainId
    }
}

/**
 * 更新供应链SKU定价
 */
class UpdateSkuPricingUseCase @Inject constructor(
    private val repository: SupplyChainItemRepository
) {
    suspend operator fun invoke(
        supplyChainId: Long,
        skuId: Long,
        skuName: String,
        price: Double,
        deposit: Double = 0.0,
        isFloating: Boolean = false
    ): Long {
        val item = SupplyChainItem(
            supplyChainId = supplyChainId,
            skuId = skuId,
            skuName = skuName,
            price = price,
            deposit = deposit,
            isFloating = isFloating
        )
        return if (repository.getBySkuId(skuId) != null) {
            repository.update(item)
            skuId
        } else {
            repository.insert(item)
        }
    }
}
