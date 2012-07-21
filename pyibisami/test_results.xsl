<?xml version="1.0" encoding="ISO-8859-1"?>

<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="/">
    <html>
        <body>
            <h2>Test Results - Summary</h2>
            <table border="1">
                <tr bgcolor="#9acd32">
                    <th>Test Name</th>
                    <th>Result</th>
                </tr>
              <xsl:for-each select="test">
                <tr>
                    <td><a href="#{name}"><xsl:value-of select="name"/></a></td>
                    <td><xsl:value-of select="result"/></td>
                </tr>
              </xsl:for-each>
            </table>
            <h2>Test Results - Details</h2>
          <xsl:for-each select="test">
              <h3><a name="{name}"><xsl:value-of select="name"/></a></h3>
          </xsl:for-each>
        </body>
    </html>
</xsl:template>

</xsl:stylesheet>

