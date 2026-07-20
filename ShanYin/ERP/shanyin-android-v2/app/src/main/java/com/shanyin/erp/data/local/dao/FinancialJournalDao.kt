package com.shanyin.erp.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.shanyin.erp.data.local.entity.FinancialJournalEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface FinancialJournalDao {
    @Query("SELECT * FROM financial_journal ORDER BY transaction_date DESC")
    fun getAll(): Flow<List<FinancialJournalEntity>>

    @Query("SELECT * FROM financial_journal WHERE id = :id")
    suspend fun getById(id: Long): FinancialJournalEntity?

    @Query("SELECT * FROM financial_journal WHERE ref_vc_id = :vcId")
    fun getByVcId(vcId: Long): Flow<List<FinancialJournalEntity>>

    @Query("SELECT * FROM financial_journal WHERE voucher_no = :voucherNo")
    fun getByVoucherNo(voucherNo: String): Flow<List<FinancialJournalEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(entity: FinancialJournalEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(entities: List<FinancialJournalEntity>): List<Long>

    @Update
    suspend fun update(entity: FinancialJournalEntity)

    @Delete
    suspend fun delete(entity: FinancialJournalEntity)

    @Query("SELECT COUNT(*) FROM financial_journal")
    fun getCount(): Flow<Int>

    /**
     * 查询以指定前缀开头的最大凭证序号
     * 用于生成顺序凭证号 JZ-202603-0001
     * @param prefix 凭证号前缀，如 "JZ-202603-"
     * @return 最大序号（无数据时返回 null）
     */
    @Query("SELECT MAX(CAST(SUBSTR(voucher_no, :prefixLength + 1) AS INTEGER)) FROM financial_journal WHERE voucher_no LIKE :prefix || '%'")
    suspend fun getMaxSeqForPrefix(prefix: String, prefixLength: Int): Int?

    /** 按科目ID查询所有分录 */
    @Query("SELECT * FROM financial_journal WHERE account_id = :accountId ORDER BY transaction_date DESC")
    fun getByAccountId(accountId: Long): Flow<List<FinancialJournalEntity>>

    /** 按日期范围查询所有分录 */
    @Query("SELECT * FROM financial_journal WHERE transaction_date BETWEEN :startDate AND :endDate ORDER BY transaction_date DESC")
    fun getByDateRange(startDate: Long, endDate: Long): Flow<List<FinancialJournalEntity>>

    /** 按日期范围和科目ID查询 */
    @Query("SELECT * FROM financial_journal WHERE account_id = :accountId AND transaction_date BETWEEN :startDate AND :endDate ORDER BY transaction_date DESC")
    fun getByAccountIdAndDateRange(accountId: Long, startDate: Long, endDate: Long): Flow<List<FinancialJournalEntity>>
}
