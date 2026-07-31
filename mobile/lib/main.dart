import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'providers/app_provider.dart';
import 'screens/inshorts_feed_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Color(0xFF0F141C),
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  runApp(const SkimTubeApp());
}

class SkimTubeApp extends StatelessWidget {
  const SkimTubeApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AppProvider(),
      child: MaterialApp(
        title: 'SkimTube',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          scaffoldBackgroundColor: const Color(0xFF0F141C),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF2563EB),
            secondary: Color(0xFFFF0000),
            surface: Color(0xFF141923),
          ),
          fontFamily: 'Roboto',
        ),
        home: const InShortsFeedScreen(),
      ),
    );
  }
}
