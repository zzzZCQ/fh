package com.fh.wework.spoof

import de.robv.android.xposed.IXposedHookLoadPackage
import de.robv.android.xposed.XposedBridge
import de.robv.android.xposed.XposedHelpers
import de.robv.android.xposed.callbacks.XC_LoadPackage
import java.io.File

/**
 * 企微iPad设备伪装模块 (Xposed)
 * 
 * 原理：Hook android.os.Build 的静态字段，
 * 以及系统API返回的设备信息，让企微APP认为当前是 iPad 设备。
 * 
 * 目标应用：com.tencent.wework（企业微信）
 */
class WeWorkDeviceSpoofer : IXposedHookLoadPackage {

    companion object {
        const val TAG = "FH_WeWorkSpoof"
        
        // 伪装配置文件路径（可被外部Python脚本动态生成）
        const val CONFIG_PATH = "/sdcard/Android/data/com.tencent.wework/files/device_spoof.json"
    }

    override fun handleLoadPackage(lpparam: XC_LoadPackage.LoadPackageParam) {
        // 只 Hook 企微APP，避免影响其他应用
        if (lpparam.packageName != "com.tencent.wework") {
            return
        }
        
        XposedBridge.log("[$TAG] 开始Hook企微: ${lpparam.packageName}")
        
        // 1. 从配置文件加载伪装参数（若无则用默认）
        val spoofConfig = loadSpoofConfig()
        
        // 2. Hook Build 静态字段（设备标识）
        hookBuildFields(spoofConfig)
        
        // 3. Hook SystemProperties（系统属性读取）
        hookSystemProperties(spoofConfig)
        
        // 4. Hook TelephonyManager（运营商信息）
        hookTelephonyManager(lpparam, spoofConfig)
        
        // 5. Hook Settings.Secure（ANDROID_ID）
        hookSecureSettings(lpparam, spoofConfig)
        
        // 6. Hook DisplayMetrics（屏幕密度，模拟iPad分辨率）
        hookDisplayMetrics(lpparam, spoofConfig)
        
        // 7. Hook PackageManager（签名与应用信息伪装-可选）
        // hookPackageManager(lpparam)
        
        XposedBridge.log("[$TAG] Hook完成 ✓")
    }

    // ───────────────────────────────────────
    // 1. 加载伪装配置
    // ───────────────────────────────────────
    private fun loadSpoofConfig(): Map<String, String> {
        val defaults = mapOf(
            // 设备标识 (iPad Pro 11-inch 2021)
            "BRAND" to "Apple",
            "MANUFACTURER" to "Apple",
            "MODEL" to "iPad Pro (11-inch)",
            "PRODUCT" to "iPad13,4",
            "DEVICE" to "iPad13,4",
            "BOARD" to "Apple Silicon",
            "HARDWARE" to "A12X Bionic",
            "CHIPSET" to "Apple A12X Bionic",
            
            // 系统版本
            "RELEASE" to "17.2",
            "SDK_INT" to "34",
            "INCREMENTAL" to "21C62",
            
            // 显示信息
            "DISPLAY" to "iPadOS 17.2 (21C62)",
            
            // 指纹（用于系统唯一标识）
            "FINGERPRINT" to "Apple/iPad13,4/iPad:17.2/21C62:user/release-keys",
            
            // 用户信息
            "USER" to "mobile_user",
            "HOST" to "ipad-pro",
            "TAGS" to "release-keys",
            "TYPE" to "user",
            
            // CPU架构（虽然iPad是arm64，模拟器是x86_64，尽量伪装）
            "CPU_ABI" to "arm64-v8a",
            "CPU_ABI2" to "",
            "SUPPORTED_ABIS" to "arm64-v8a,armeabi-v7a,armeabi",
            
            // 唯一标识
            "ANDROID_ID" to "9774d56d682e549c",  // 固定ID，避免被检测
            
            // 网络与运营商
            "NETWORK_OPERATOR" to "46000",
            "NETWORK_OPERATOR_NAME" to "中国移动",
            "SIM_OPERATOR" to "46000",
            "SIM_OPERATOR_NAME" to "中国移动",
            "NETWORK_COUNTRY_ISO" to "cn",
            "NETWORK_TYPE" to "13",  // LTE
            "PHONE_TYPE" to "1",    // GSM
            
            // 屏幕密度（iPad Pro 11-inch: 264 dpi）
            "DENSITY_DPI" to "264",
            "SCREEN_WIDTH" to "1668",
            "SCREEN_HEIGHT" to "2388",
            
            // User-Agent组件
            "USER_AGENT_APPEND" to " MicroMessenger/8.0.44.262(0x28002C39) NetType/WIFI Language/zh_CN"
        )
        
        // 尝试从外部配置文件读取（支持动态修改）
        return try {
            val configFile = File(CONFIG_PATH)
            if (configFile.exists()) {
                val json = org.json.JSONObject(configFile.readText())
                val merged = defaults.toMutableMap()
                json.keys().forEach { key ->
                    merged[key] = json.getString(key)
                }
                XposedBridge.log("[$TAG] 已加载自定义配置: ${merged.size}项")
                merged
            } else {
                XposedBridge.log("[$TAG] 使用默认配置（${CONFIG_PATH}不存在）")
                defaults
            }
        } catch (e: Exception) {
            XposedBridge.log("[$TAG] 配置读取失败，使用默认: ${e.message}")
            defaults
        }
    }

    // ───────────────────────────────────────
    // 2. Hook android.os.Build 字段
    // ───────────────────────────────────────
    private fun hookBuildFields(config: Map<String, String>) {
        try {
            val buildClass = XposedHelpers.findClass("android.os.Build", null)
            
            // Hook 常用字段
            mapOf(
                "BRAND" to config["BRAND"],
                "MANUFACTURER" to config["MANUFACTURER"],
                "MODEL" to config["MODEL"],
                "PRODUCT" to config["PRODUCT"],
                "DEVICE" to config["DEVICE"],
                "BOARD" to config["BOARD"],
                "HARDWARE" to config["HARDWARE"],
                "RELEASE" to config["RELEASE"],
                "DISPLAY" to config["DISPLAY"],
                "FINGERPRINT" to config["FINGERPRINT"],
                "USER" to config["USER"],
                "HOST" to config["HOST"],
                "TAGS" to config["TAGS"],
                "TYPE" to config["TYPE"],
                "CPU_ABI" to config["CPU_ABI"],
                "CPU_ABI2" to config["CPU_ABI2"]
            ).forEach { (field, value) ->
                if (value != null) {
                    try {
                        XposedHelpers.setStaticObjectField(buildClass, field, value)
                        XposedBridge.log("[$TAG] 伪装 $field = $value")
                    } catch (e: Throwable) {
                        XposedBridge.log("[$TAG] Hook $field 失败: ${e.message}")
                    }
                }
            }
            
            // Hook Build.VERSION
            val versionClass = XposedHelpers.findClass("android.os.Build.VERSION", null)
            config["RELEASE"]?.let { XposedHelpers.setStaticObjectField(versionClass, "RELEASE", it) }
            config["INCREMENTAL"]?.let { XposedHelpers.setStaticObjectField(versionClass, "INCREMENTAL", it) }
            config["SDK_INT"]?.let { XposedHelpers.setStaticIntField(versionClass, "SDK_INT", it.toInt()) }
            
            XposedBridge.log("[$TAG] Build字段Hook完成")
        } catch (e: Throwable) {
            XposedBridge.log("[$TAG] Build Hook 异常: ${e.message}")
        }
    }

    // ───────────────────────────────────────
    // 3. Hook SystemProperties
    // ───────────────────────────────────────
    private fun hookSystemProperties(config: Map<String, String>) {
        try {
            val sysPropsClass = XposedHelpers.findClass("android.os.SystemProperties", null)
            
            // Hook get(String) 方法
            XposedHelpers.findAndHookMethod(
                sysPropsClass, "get",
                String::class.java,
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        val key = param.args[0] as? String ?: return
                        
                        // 替换特定属性
                        val replacement = when (key) {
                            "ro.product.brand" -> config["BRAND"]
                            "ro.product.manufacturer" -> config["MANUFACTURER"]
                            "ro.product.model" -> config["MODEL"]
                            "ro.product.name" -> config["PRODUCT"]
                            "ro.product.device" -> config["DEVICE"]
                            "ro.product.board" -> config["BOARD"]
                            "ro.product.hardware" -> config["HARDWARE"]
                            "ro.build.version.release" -> config["RELEASE"]
                            "ro.build.version.sdk" -> config["SDK_INT"]
                            "ro.build.fingerprint" -> config["FINGERPRINT"]
                            "ro.build.display.id" -> config["DISPLAY"]
                            "ro.product.cpu.abi" -> config["CPU_ABI"]
                            else -> null
                        }
                        
                        if (replacement != null) {
                            param.result = replacement
                        }
                    }
                }
            )
            
            // Hook get(String, String) 方法（带默认值版本）
            XposedHelpers.findAndHookMethod(
                sysPropsClass, "get",
                String::class.java, String::class.java,
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        val key = param.args[0] as? String ?: return
                        
                        val replacement = when (key) {
                            "ro.product.brand" -> config["BRAND"]
                            "ro.product.manufacturer" -> config["MANUFACTURER"]
                            "ro.product.model" -> config["MODEL"]
                            "ro.product.name" -> config["PRODUCT"]
                            "ro.product.device" -> config["DEVICE"]
                            "ro.build.version.release" -> config["RELEASE"]
                            "ro.build.version.sdk" -> config["SDK_INT"]
                            "ro.build.fingerprint" -> config["FINGERPRINT"]
                            else -> null
                        }
                        
                        if (replacement != null) {
                            param.result = replacement
                        }
                    }
                }
            )
            
            XposedBridge.log("[$TAG] SystemProperties Hook完成")
        } catch (e: Throwable) {
            XposedBridge.log("[$TAG] SystemProperties Hook异常: ${e.message}")
        }
    }

    // ───────────────────────────────────────
    // 4. Hook TelephonyManager (运营商信息)
    // ───────────────────────────────────────
    private fun hookTelephonyManager(lpparam: XC_LoadPackage.LoadPackageParam, config: Map<String, String>) {
        try {
            val telClass = XposedHelpers.findClass("android.telephony.TelephonyManager", lpparam.classLoader)
            
            // Hook getNetworkOperator
            XposedHelpers.findAndHookMethod(
                telClass, "getNetworkOperator",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = config["NETWORK_OPERATOR"]
                    }
                }
            )
            
            // Hook getNetworkOperatorName
            XposedHelpers.findAndHookMethod(
                telClass, "getNetworkOperatorName",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = config["NETWORK_OPERATOR_NAME"]
                    }
                }
            )
            
            // Hook getSimOperator
            XposedHelpers.findAndHookMethod(
                telClass, "getSimOperator",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = config["SIM_OPERATOR"]
                    }
                }
            )
            
            // Hook getSimOperatorName
            XposedHelpers.findAndHookMethod(
                telClass, "getSimOperatorName",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = config["SIM_OPERATOR_NAME"]
                    }
                }
            )
            
            // Hook getNetworkCountryIso
            XposedHelpers.findAndHookMethod(
                telClass, "getNetworkCountryIso",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = config["NETWORK_COUNTRY_ISO"]
                    }
                }
            )
            
            // Hook getNetworkType
            XposedHelpers.findAndHookMethod(
                telClass, "getNetworkType",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = config["NETWORK_TYPE"]?.toIntOrNull() ?: 13
                    }
                }
            )
            
            // Hook getPhoneType
            XposedHelpers.findAndHookMethod(
                telClass, "getPhoneType",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = config["PHONE_TYPE"]?.toIntOrNull() ?: 1
                    }
                }
            )
            
            // Hook getDeviceId (IMEI) - 返回空或固定值
            XposedHelpers.findAndHookMethod(
                telClass, "getDeviceId",
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        param.result = ""  // 空IMEI，避免被识别为模拟器
                    }
                }
            )
            
            // Hook getImei (Android 10+)
            try {
                XposedHelpers.findAndHookMethod(
                    telClass, "getImei",
                    object : de.robv.android.xposed.XC_MethodHook() {
                        override fun afterHookedMethod(param: MethodHookParam) {
                            param.result = ""
                        }
                    }
                )
            } catch (_: Throwable) { /* 旧版本没有此方法 */ }
            
            XposedBridge.log("[$TAG] TelephonyManager Hook完成")
        } catch (e: Throwable) {
            XposedBridge.log("[$TAG] TelephonyManager Hook异常: ${e.message}")
        }
    }

    // ───────────────────────────────────────
    // 5. Hook Settings.Secure (ANDROID_ID)
    // ───────────────────────────────────────
    private fun hookSecureSettings(lpparam: XC_LoadPackage.LoadPackageParam, config: Map<String, String>) {
        try {
            val secureClass = XposedHelpers.findClass("android.provider.Settings\$Secure", lpparam.classLoader)
            
            XposedHelpers.findAndHookMethod(
                secureClass, "getString",
                android.content.ContentResolver::class.java, String::class.java,
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        val key = param.args[1] as? String ?: return
                        if (key == "android_id") {
                            param.result = config["ANDROID_ID"]
                        }
                    }
                }
            )
            
            XposedBridge.log("[$TAG] Settings.Secure Hook完成")
        } catch (e: Throwable) {
            XposedBridge.log("[$TAG] Settings.Secure Hook异常: ${e.message}")
        }
    }

    // ───────────────────────────────────────
    // 6. Hook DisplayMetrics (屏幕密度)
    // ───────────────────────────────────────
    private fun hookDisplayMetrics(lpparam: XC_LoadPackage.LoadPackageParam, config: Map<String, String>) {
        try {
            val metricsClass = XposedHelpers.findClass("android.util.DisplayMetrics", lpparam.classLoader)
            
            // Hook getMetrics 方法（在WindowManager和Resources中）
            XposedHelpers.findAndHookConstructor(
                metricsClass,
                object : de.robv.android.xposed.XC_MethodHook() {
                    override fun afterHookedMethod(param: MethodHookParam) {
                        // 构造完成后，设置伪装的密度
                        try {
                            XposedHelpers.setIntField(param.thisObject, "densityDpi", config["DENSITY_DPI"]?.toIntOrNull() ?: 264)
                            XposedHelpers.setIntField(param.thisObject, "widthPixels", config["SCREEN_WIDTH"]?.toIntOrNull() ?: 1668)
                            XposedHelpers.setIntField(param.thisObject, "heightPixels", config["SCREEN_HEIGHT"]?.toIntOrNull() ?: 2388)
                        } catch (_: Throwable) { /* 静默失败 */ }
                    }
                }
            )
            
            XposedBridge.log("[$TAG] DisplayMetrics Hook完成")
        } catch (e: Throwable) {
            XposedBridge.log("[$TAG] DisplayMetrics Hook异常: ${e.message}")
        }
    }
}
