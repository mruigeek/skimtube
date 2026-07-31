allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}
subprojects {
    project.evaluationDependsOn(":app")
}

subprojects {
    val configureAndroid = { proj: Project ->
        val android = proj.extensions.findByName("android")
        if (android != null) {
            try {
                val compileSdkVersionMethod = android.javaClass.getMethod("compileSdkVersion", Int::class.java)
                compileSdkVersionMethod.invoke(android, 36)
                println("Successfully set compileSdkVersion to 36 for subproject ${proj.name}")
            } catch (e: Exception) {
                try {
                    val setCompileSdkMethod = android.javaClass.getMethod("setCompileSdk", Int::class.java)
                    setCompileSdkMethod.invoke(android, 36)
                    println("Successfully set compileSdk to 36 for subproject ${proj.name}")
                } catch (e2: Exception) {}
            }
        }
    }

    if (state.executed) {
        configureAndroid(this)
    } else {
        afterEvaluate {
            configureAndroid(this)
        }
    }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
