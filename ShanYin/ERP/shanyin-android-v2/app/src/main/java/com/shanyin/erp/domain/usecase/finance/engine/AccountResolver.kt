package com.shanyin.erp.domain.usecase.finance.engine

import com.shanyin.erp.domain.repository.FinanceAccountRepository
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 将 AccountConfig 中的科目名称（level1Name）解析为数据库中的 accountId
 *
 * 预置账户需要在数据库的 finance_accounts 表中提前插入：
 * - 银行存款
 * - 应付账款-设备款
 * - 应付账款-物料款
 * - 其他应付款-押金
 * - 应收账款-客户
 * - 预付账款-供应商
 * - 预收账款-客户
 * - 其他应付款-罚款
 */
@Singleton
class AccountResolver @Inject constructor(
    private val financeAccountRepo: FinanceAccountRepository
) {
    /**
     * 根据科目名称（level1Name）查找 accountId
     * @param level1Name 科目名称（精确匹配 finance_accounts.level1_name）
     * @return accountId，未找到时返回 null
     */
    suspend fun resolveId(level1Name: String): Long? {
        val accounts = financeAccountRepo.getAll().first()
        return accounts.find { it.level1Name == level1Name }?.id
    }

    /**
     * 根据科目名称查找，找不到时抛出异常（应在数据初始化时保证科目存在）
     */
    suspend fun resolveIdOrThrow(level1Name: String): Long {
        return resolveId(level1Name)
            ?: throw IllegalStateException("Finance account not found: $level1Name. Please ensure account is seeded in finance_accounts table.")
    }

}
