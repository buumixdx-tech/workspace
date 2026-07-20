package com.shanyin.erp.data.repository

import android.net.Uri
import androidx.sqlite.db.SupportSQLiteDatabase
import com.shanyin.erp.data.local.AppDatabase
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

/** 导入进度事件 */
sealed class ImportEvent {
    data object Idle : ImportEvent()
    data class Progress(val table: String, val current: Int, val total: Int) : ImportEvent()
    data class Success(val totalRows: Int) : ImportEvent()
    data class Error(val message: String) : ImportEvent()
}

private val TABLE_ORDER = listOf(
    "channel_customers",
    "suppliers",
    "contracts",
    "finance_accounts",
    "external_partners",
    "bank_accounts",
    "time_rules",
    "system_events",
    "points",
    "skus",
    "business",
    "supply_chains",
    "material_inventory",
    "supply_chain_items",
    "virtual_contracts",
    "equipment_inventory",
    "vc_status_logs",
    "financial_journal",
    "logistics",
    "cash_flows",
    "vc_history",
    "express_orders",
    "cash_flow_ledger"
)

@Singleton
class JsonImportRepository @Inject constructor(
    @ApplicationContext private val context: android.content.Context,
    private val appDatabase: AppDatabase
) {
    fun importFromJson(uri: Uri): Flow<ImportEvent> = flow {
        emit(ImportEvent.Idle)

        // 1. 读取 JSON
        val jsonText = withContext(Dispatchers.IO) {
            context.contentResolver.openInputStream(uri)?.use { input ->
                input.bufferedReader(Charsets.UTF_8).readText()
            } ?: throw IllegalStateException("无法读取文件")
        }

        val root = JSONObject(jsonText)
        val tablesObj = root.optJSONObject("tables")
            ?: throw IllegalStateException("JSON 格式错误：缺少 tables 节点")

        // 2. 执行导入
        val result = importAllTables(tablesObj)

        for ((table, tableIndex, totalTables) in result.progressList) {
            emit(ImportEvent.Progress(table, tableIndex, totalTables))
        }
        emit(ImportEvent.Success(result.totalRows))
    }

    private suspend fun importAllTables(tablesObj: JSONObject): ImportResult {
        return withContext(Dispatchers.IO) {
            // 使用 Room 的 SupportSQLiteDatabase，所有变更都会触发 Room Flow 重新查询
            val db: SupportSQLiteDatabase = appDatabase.openHelper.writableDatabase

            val progressList = mutableListOf<Triple<String, Int, Int>>()
            var count = 0

            db.execSQL("PRAGMA foreign_keys = OFF")
            db.beginTransaction()
            try {
                for ((idx, table) in TABLE_ORDER.withIndex()) {
                    if (!tablesObj.has(table)) continue
                    val rows: JSONArray = tablesObj.getJSONArray(table)
                    val rowCount = rows.length()
                    if (rowCount == 0) continue

                    db.execSQL("DELETE FROM $table")

                    val firstRow = rows.getJSONObject(0)
                    val columnNames = firstRow.keys().asSequence().toList()

                    for (i in 0 until rowCount) {
                        val row = rows.getJSONObject(i)
                        val values = columnNames.map { col ->
                            if (row.has(col) && !row.isNull(col)) {
                                when (val v = row.get(col)) {
                                    is Number -> if (v is Double || v is Float) v.toDouble() else v.toLong()
                                    is Boolean -> if (v) 1L else 0L
                                    else -> v.toString()
                                }
                            } else null
                        }.toMutableList()

                        val placeholders = columnNames.indices.joinToString(", ") { "?" }
                        val sql = "INSERT INTO $table (${columnNames.joinToString(",")}) VALUES ($placeholders)"
                        @Suppress("UNCHECKED_CAST")
                        db.execSQL(sql, values.toTypedArray())
                        count++
                    }
                    progressList.add(Triple(table, idx + 1, TABLE_ORDER.size))
                }
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
                db.execSQL("PRAGMA foreign_keys = ON")
            }

            // 补充 supply_chain_items.deposit
            updateSupplyChainItemDeposits(db, tablesObj)

            ImportResult(progressList, count)
        }
    }

    private fun updateSupplyChainItemDeposits(db: SupportSQLiteDatabase, tablesObj: JSONObject) {
        val pricingDeposits = mutableMapOf<String, Double>()
        val businessRows = tablesObj.optJSONArray("business") ?: return
        for (i in 0 until businessRows.length()) {
            val business = businessRows.getJSONObject(i)
            val detailsStr = business.optString("details", "")
            if (detailsStr.isEmpty()) continue
            try {
                val details = JSONObject(detailsStr)
                val pricing = details.optJSONObject("pricing") ?: continue
                pricing.keys().forEach { skuName ->
                    val info = pricing.getJSONObject(skuName)
                    val deposit = info.optDouble("deposit", 0.0)
                    if (deposit > 0) {
                        pricingDeposits[skuName] = deposit
                    }
                }
            } catch (e: Exception) {
                // 忽略解析错误
            }
        }

        if (pricingDeposits.isEmpty()) return

        val skuNameToId = mutableMapOf<String, Long>()
        val cursor = db.query("SELECT id, name FROM skus")
        while (cursor.moveToNext()) {
            val id = cursor.getLong(0)
            val name = cursor.getString(1) ?: ""
            skuNameToId[name] = id
        }
        cursor.close()

        val skuIdToDeposit = mutableMapOf<Long, Double>()
        pricingDeposits.forEach { (skuName, deposit) ->
            val skuId = skuNameToId[skuName]
            if (skuId != null) {
                skuIdToDeposit[skuId] = deposit
            }
        }

        if (skuIdToDeposit.isEmpty()) return

        skuIdToDeposit.forEach { (skuId, deposit) ->
            db.execSQL(
                "UPDATE supply_chain_items SET deposit = ? WHERE sku_id = ?",
                arrayOf(deposit, skuId)
            )
        }
    }

    private data class ImportResult(
        val progressList: List<Triple<String, Int, Int>>,
        val totalRows: Int
    )
}
