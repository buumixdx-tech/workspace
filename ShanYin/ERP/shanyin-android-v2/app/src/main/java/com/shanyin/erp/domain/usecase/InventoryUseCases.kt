package com.shanyin.erp.domain.usecase

import com.shanyin.erp.domain.model.*
import com.shanyin.erp.domain.repository.EquipmentInventoryRepository
import com.shanyin.erp.domain.repository.MaterialInventoryRepository
import com.shanyin.erp.domain.repository.SkuRepository
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

// ==================== Equipment Inventory Use Cases ====================

class GetAllEquipmentInventoryUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    operator fun invoke(): Flow<List<EquipmentInventory>> = repository.getAll()
}

class GetEquipmentInventoryByIdUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    suspend operator fun invoke(id: Long): EquipmentInventory? = repository.getById(id)
}

class GetEquipmentInventoryByVcUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    operator fun invoke(vcId: Long): Flow<List<EquipmentInventory>> = repository.getByVcId(vcId)
}

class GetEquipmentInventoryByPointUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    operator fun invoke(pointId: Long): Flow<List<EquipmentInventory>> = repository.getByPointId(pointId)
}

class GetEquipmentInventoryByStatusUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    operator fun invoke(status: OperationalStatus): Flow<List<EquipmentInventory>> =
        repository.getByOperationalStatus(status)
}

class GetEquipmentInventoryBySnUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    suspend operator fun invoke(sn: String): EquipmentInventory? = repository.getBySn(sn)
}

class SaveEquipmentInventoryUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    suspend operator fun invoke(equipment: EquipmentInventory): Long {
        return if (equipment.id == 0L) {
            repository.insert(equipment)
        } else {
            repository.update(equipment)
            equipment.id
        }
    }
}

class DeleteEquipmentInventoryUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    suspend operator fun invoke(equipment: EquipmentInventory) = repository.delete(equipment)
}

class UpdateEquipmentStatusUseCase @Inject constructor(
    private val repository: EquipmentInventoryRepository
) {
    suspend operator fun invoke(
        equipmentId: Long,
        operationalStatus: OperationalStatus? = null,
        deviceStatus: DeviceStatus? = null
    ): Long {
        val equipment = repository.getById(equipmentId) ?: throw IllegalArgumentException("Equipment not found")
        val updated = equipment.copy(
            operationalStatus = operationalStatus ?: equipment.operationalStatus,
            deviceStatus = deviceStatus ?: equipment.deviceStatus
        )
        repository.update(updated)
        return equipmentId
    }
}

// ==================== Material Inventory Use Cases ====================

class GetAllMaterialInventoryUseCase @Inject constructor(
    private val repository: MaterialInventoryRepository
) {
    operator fun invoke(): Flow<List<MaterialInventory>> = repository.getAll()
}

class GetMaterialInventoryByIdUseCase @Inject constructor(
    private val repository: MaterialInventoryRepository
) {
    suspend operator fun invoke(id: Long): MaterialInventory? = repository.getById(id)
}

class GetMaterialInventoryBySkuUseCase @Inject constructor(
    private val repository: MaterialInventoryRepository
) {
    suspend operator fun invoke(skuId: Long): MaterialInventory? = repository.getBySkuId(skuId)
}

class SaveMaterialInventoryUseCase @Inject constructor(
    private val repository: MaterialInventoryRepository
) {
    suspend operator fun invoke(material: MaterialInventory): Long {
        return if (material.id == 0L) {
            repository.insert(material)
        } else {
            repository.update(material)
            material.id
        }
    }
}

class DeleteMaterialInventoryUseCase @Inject constructor(
    private val repository: MaterialInventoryRepository
) {
    suspend operator fun invoke(material: MaterialInventory) = repository.delete(material)
}

// ==================== Inventory Operations Use Cases ====================

class UpdateStockDistributionUseCase @Inject constructor(
    private val repository: MaterialInventoryRepository,
    private val skuRepository: SkuRepository
) {
    suspend operator fun invoke(
        skuId: Long,
        pointId: Long,
        pointName: String,
        quantity: Int,
        averagePrice: Double = 0.0
    ): Long {
        val sku = skuRepository.getById(skuId) ?: throw IllegalArgumentException("SKU not found")
        val existing = repository.getBySkuId(skuId)

        val currentDistribution = existing?.stockDistribution?.toMutableList() ?: mutableListOf()
        val existingIndex = currentDistribution.indexOfFirst { it.pointId == pointId }

        if (existingIndex >= 0) {
            val existingEntry = currentDistribution[existingIndex]
            currentDistribution[existingIndex] = existingEntry.copy(quantity = quantity)
        } else {
            currentDistribution.add(StockDistribution(pointId = pointId, pointName = pointName, quantity = quantity))
        }

        val totalBalance = currentDistribution.sumOf { it.quantity.toDouble() * averagePrice }
            .let { if (it == 0.0) existing?.totalBalance ?: 0.0 else it }

        val material = MaterialInventory(
            id = existing?.id ?: 0L,
            skuId = skuId,
            skuName = sku.name,
            stockDistribution = currentDistribution,
            averagePrice = averagePrice,
            totalBalance = totalBalance
        )

        return if (existing != null) {
            repository.update(material)
            existing.id
        } else {
            repository.insert(material)
        }
    }
}

class TransferInventoryUseCase @Inject constructor(
    private val repository: MaterialInventoryRepository
) {
    suspend operator fun invoke(
        skuId: Long,
        fromPointId: Long,
        fromPointName: String,
        toPointId: Long,
        toPointName: String,
        quantity: Int
    ): Long {
        val existing = repository.getBySkuId(skuId)
            ?: throw IllegalArgumentException("Material inventory not found for SKU")

        val fromDistribution = existing.stockDistribution.toMutableList()
        val fromIndex = fromDistribution.indexOfFirst { it.pointId == fromPointId }
        if (fromIndex < 0) throw IllegalArgumentException("Source warehouse not found")
        if (fromDistribution[fromIndex].quantity < quantity) throw IllegalArgumentException("Insufficient stock")

        fromDistribution[fromIndex] = fromDistribution[fromIndex].copy(
            quantity = fromDistribution[fromIndex].quantity - quantity
        )

        val toDistribution = existing.stockDistribution.toMutableList()
        val toIndex = toDistribution.indexOfFirst { it.pointId == toPointId }
        if (toIndex >= 0) {
            toDistribution[toIndex] = toDistribution[toIndex].copy(
                quantity = toDistribution[toIndex].quantity + quantity
            )
        } else {
            toDistribution.add(StockDistribution(pointId = toPointId, pointName = toPointName, quantity = quantity))
        }

        val updated = existing.copy(stockDistribution = fromDistribution + toDistribution.filter { d ->
            d.pointId != fromPointId || fromDistribution.find { it.pointId == fromPointId }?.quantity ?: 0 > 0
        }.let { list ->
            val fromEntry = list.find { it.pointId == fromPointId }
            val toEntry = list.find { it.pointId == toPointId }
            list.filter { it.pointId != fromPointId && it.pointId != toPointId } +
                listOfNotNull(fromEntry, toEntry)
        })

        repository.update(updated)
        return existing.id
    }
}
