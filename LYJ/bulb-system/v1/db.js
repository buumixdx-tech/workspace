// IndexedDB 数据库模块 - 会议室灯泡管理系统专用
const DB_NAME = 'bulb_system_db';
const DB_VERSION = 1;
const STORE_NAME = 'data';

let db = null;

// ==================== 数据库基础操作 ====================

function openDB() {
    return new Promise((resolve, reject) => {
        if (db) {
            resolve(db);
            return;
        }
        let request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            db = request.result;
            resolve(db);
        };
        request.onupgradeneeded = (event) => {
            let database = event.target.result;
            if (!database.objectStoreNames.contains(STORE_NAME)) {
                database.createObjectStore(STORE_NAME, { keyPath: 'key' });
            }
        };
    });
}

function getData(key) {
    return openDB().then(database => {
        return new Promise((resolve, reject) => {
            let transaction = database.transaction([STORE_NAME], 'readonly');
            let store = transaction.objectStore(STORE_NAME);
            let request = store.get(key);
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result ? request.result.value : null);
        });
    });
}

function setData(key, value) {
    return openDB().then(database => {
        return new Promise((resolve, reject) => {
            let transaction = database.transaction([STORE_NAME], 'readwrite');
            let store = transaction.objectStore(STORE_NAME);
            let request = store.put({ key, value });
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
        });
    });
}

function removeData(key) {
    return openDB().then(database => {
        return new Promise((resolve, reject) => {
            let transaction = database.transaction([STORE_NAME], 'readwrite');
            let store = transaction.objectStore(STORE_NAME);
            let request = store.delete(key);
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve();
        });
    });
}

// ==================== 用户管理 ====================

const DEFAULT_USERS = [
    { username: 'admin', password: '123456', role: '管理员' },
    { username: 'huifu', password: '123456', role: '会服专员' },
    { username: 'zhuguan', password: '123456', role: '会服主管' },
    { username: 'zichan', password: '123456', role: '资产管理员' },
    { username: 'gongyingshang', password: '123456', role: '供应商' }
];

async function getUserList() {
    let data = await getData('userList');
    if (!data) {
        await setData('userList', JSON.stringify(DEFAULT_USERS));
        return DEFAULT_USERS;
    }
    return JSON.parse(data);
}

async function setUserList(userList) {
    await setData('userList', JSON.stringify(userList));
}

async function addUser(user) {
    let userList = await getUserList();
    userList.push(user);
    await setUserList(userList);
    return userList;
}

async function deleteUser(username) {
    let userList = await getUserList();
    userList = userList.filter(u => u.username !== username);
    await setUserList(userList);
    return userList;
}

async function findUser(username, password) {
    let userList = await getUserList();
    return userList.find(u => u.username === username && u.password === password);
}

// ==================== 台账记录 ====================

async function getRecordList() {
    let data = await getData('recordList');
    return data ? JSON.parse(data) : [];
}

async function addRecord(record) {
    let recordList = await getRecordList();
    recordList.unshift(record);
    await setData('recordList', JSON.stringify(recordList));
    return recordList;
}

async function setRecordList(recordList) {
    await setData('recordList', JSON.stringify(recordList));
}

// ==================== 库存管理 ====================

async function getStock() {
    let data = await getData('stock');
    return data ? parseInt(data) : 10;
}

async function setStock(num) {
    await setData('stock', num.toString());
}

async function reduceStock(num) {
    let stock = await getStock();
    stock -= num;
    await setStock(stock);
    return stock;
}

async function addStock(num) {
    let stock = await getStock();
    stock += num;
    await setStock(stock);
    return stock;
}

// ==================== 供应商订单 ====================

async function getSupplyOrder() {
    return await getData('supplyOrder');
}

async function setSupplyOrder(order) {
    await setData('supplyOrder', order);
}

async function clearSupplyOrder() {
    await removeData('supplyOrder');
}

// ==================== 管理员登录状态 ====================

async function getCurrentAdmin() {
    let user = await getData('currentAdminUser');
    let role = await getData('currentAdminRole');
    if (user && role) {
        return { username: user, role: role };
    }
    return null;
}

async function setCurrentAdmin(username, role) {
    await setData('currentAdminUser', username);
    await setData('currentAdminRole', role);
}

async function clearCurrentAdmin() {
    await removeData('currentAdminUser');
    await removeData('currentAdminRole');
}

// ==================== 会服端登录状态 ====================

async function getCurrentReportUser() {
    return await getData('currentReportUser');
}

async function setCurrentReportUser(username) {
    await setData('currentReportUser', username);
}

async function clearCurrentReportUser() {
    await removeData('currentReportUser');
}

// ==================== 初始化 ====================

async function initDefaultData() {
    await getUserList(); // 确保用户列表已初始化
    await getStock();    // 确保库存已初始化
}
