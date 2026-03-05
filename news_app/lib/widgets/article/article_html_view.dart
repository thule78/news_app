import 'package:flutter/material.dart';

import '../../core/utils/html_utils.dart';

class ArticleHtmlView extends StatelessWidget {
  const ArticleHtmlView({super.key, required this.html});

  final String html;

  @override
  Widget build(BuildContext context) {
    return Text(
      HtmlUtils.stripHtml(html),
      style: Theme.of(context).textTheme.bodyLarge,
    );
  }
}
