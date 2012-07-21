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
                    <th>Description</th>
                </tr>
              <xsl:for-each select="tests/test">
                <tr>
                    <td><a href="#{name}"><xsl:value-of select="name"/></a></td>
                    <td><xsl:value-of select="result"/></td>
                    <td><xsl:value-of select="description"/></td>
                </tr>
              </xsl:for-each>
            </table>
            <h2>Test Results - Details</h2>
          <xsl:for-each select="tests/test">
              <h3><a name="{name}"><xsl:value-of select="name"/></a></h3>
              <xsl:value-of select="description"/>
              <xsl:for-each select="output/block">
                  <h4><xsl:value-of select="./@name"/></h4>
                  <xsl:choose>
                      <xsl:when test="@type = 'text'">
                          <pre><xsl:value-of select="."/></pre>
                      </xsl:when>
                      <xsl:when test="@type = 'image'">
                          <img src="{.}"/>
                      </xsl:when>
                      <xsl:otherwise>
                          <xsl:value-of select="."/>
                      </xsl:otherwise>
                  </xsl:choose>
              </xsl:for-each>
          </xsl:for-each>
        </body>
    </html>
</xsl:template>

</xsl:stylesheet>

